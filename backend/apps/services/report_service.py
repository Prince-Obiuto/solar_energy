"""PostgreSQL-backed history, analytics, and audited report exports."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.models.persistence import (
    AreaRecord, BatteryReadingRecord, BreakerReadingRecord, DeviceRecord,
    GridReadingRecord, InverterReadingRecord, SolarReadingRecord, SystemEventRecord,
    UserRecord,
)
from apps.schemas.report import (
    Aggregation, HistoryPoint, HistoryQuery, HistoryResponse, HistorySource,
    ReportQuery, TechnicalReport,
)


@dataclass(frozen=True)
class Metric:
    field: str
    name: str
    cumulative: bool = False


SOURCE_MODELS = {
    HistorySource.SOLAR: (
        SolarReadingRecord,
        [Metric("total_power_w", "power_w"), Metric("daily_energy_kwh", "daily_energy_kwh", True), Metric("monthly_energy_kwh", "monthly_energy_kwh", True), Metric("total_energy_kwh", "total_energy_kwh", True), Metric("connected", "connected")],
    ),
    HistorySource.INVERTER: (
        InverterReadingRecord,
        [Metric("output_power_w", "output_power_w"), Metric("output_voltage", "output_voltage_v"), Metric("output_frequency", "output_frequency_hz"), Metric("load_percentage", "load_percentage"), Metric("status", "operating_state")],
    ),
    HistorySource.BATTERY: (
        BatteryReadingRecord,
        [Metric("soc", "soc_percent"), Metric("voltage", "voltage_v"), Metric("power_w", "power_w"), Metric("charging_current", "charging_current_a"), Metric("discharge_current", "discharge_current_a"), Metric("status", "state")],
    ),
    HistorySource.GRID: (
        GridReadingRecord,
        [Metric("voltage", "voltage_v"), Metric("frequency", "frequency_hz"), Metric("power_w", "power_w")],
    ),
    HistorySource.AREAS: (
        BreakerReadingRecord,
        [Metric("voltage_v", "voltage_v"), Metric("current_a", "current_a"), Metric("power_w", "power_w"), Metric("switch_state", "breaker_state"), Metric("accumulated_energy", "accumulated_energy", True)],
    ),
}
STATE_FIELDS = {"connected", "status", "switch_state"}


class HistoryAccessError(PermissionError):
    pass


class HistoryService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def query(self, query: HistoryQuery) -> HistoryResponse:
        model, metrics = SOURCE_MODELS[query.source]
        if query.aggregation is Aggregation.RAW:
            points = self._raw(query, model, metrics)
        else:
            points = self._aggregated(query, model, metrics)
        return HistoryResponse(
            source=query.source, aggregation=query.aggregation,
            from_=query.from_, to=query.to, items=points, total=len(points),
        )

    def _base_filters(self, statement, query: HistoryQuery, model):
        if query.from_ is not None:
            statement = statement.where(model.timestamp >= query.from_)
        if query.to is not None:
            statement = statement.where(model.timestamp <= query.to)
        if query.device_id is not None:
            statement = statement.where(DeviceRecord.external_reference == query.device_id)
        if query.area_id is not None:
            statement = statement.where(DeviceRecord.area_id == query.area_id)
        return statement

    def _raw(self, query: HistoryQuery, model, metrics: list[Metric]) -> list[HistoryPoint]:
        statement = (
            select(model, DeviceRecord.external_reference, AreaRecord.id, AreaRecord.name)
            .join(DeviceRecord, model.device_id == DeviceRecord.id)
            .outerjoin(AreaRecord, DeviceRecord.area_id == AreaRecord.id)
            .order_by(model.timestamp.asc())
            .limit(query.limit)
        )
        rows = self.session.execute(self._base_filters(statement, query, model)).all()
        points = []
        for record, device_reference, area_id, area_name in rows:
            values = {metric.name: getattr(record, metric.field) for metric in metrics}
            if query.source is HistorySource.GRID:
                values["available"] = None if record.voltage is None else record.voltage > 0
            points.append(HistoryPoint(
                timestamp=record.timestamp, source=query.source, device_id=device_reference,
                area_id=area_id, area=area_name, metrics=values,
            ))
        return points

    def _aggregated(self, query: HistoryQuery, model, metrics: list[Metric]) -> list[HistoryPoint]:
        bucket = self._bucket(model.timestamp, query.aggregation).label("bucket")
        expressions = []
        selected_metrics = []
        for metric in metrics:
            if metric.field in STATE_FIELDS:
                continue
            column = getattr(model, metric.field)
            expression = (func.max(column) if metric.cumulative else func.avg(column)).label(metric.name)
            expressions.append(expression)
            selected_metrics.append(metric)
        statement = (
            select(bucket, DeviceRecord.external_reference, AreaRecord.id, AreaRecord.name, *expressions)
            .join(DeviceRecord, model.device_id == DeviceRecord.id)
            .outerjoin(AreaRecord, DeviceRecord.area_id == AreaRecord.id)
            .group_by(bucket, DeviceRecord.external_reference, AreaRecord.id, AreaRecord.name)
            .order_by(bucket.asc())
            .limit(query.limit)
        )
        rows = self.session.execute(self._base_filters(statement, query, model)).all()
        points = []
        for row in rows:
            timestamp = self._bucket_timestamp(row[0])
            values = {metric.name: row[index + 4] for index, metric in enumerate(selected_metrics)}
            for metric in metrics:
                if metric.field in STATE_FIELDS:
                    values[metric.name] = None
            if query.source is HistorySource.GRID:
                values["available"] = None
            points.append(HistoryPoint(
                timestamp=timestamp, source=query.source, device_id=row[1],
                area_id=row[2], area=row[3], metrics=values,
            ))
        return points

    def _bucket(self, column, aggregation: Aggregation):
        dialect = self.session.bind.dialect.name
        if dialect == "postgresql":
            return func.date_trunc(aggregation.value, column)
        formats = {
            Aggregation.MINUTE: "%Y-%m-%dT%H:%M:00",
            Aggregation.HOUR: "%Y-%m-%dT%H:00:00",
            Aggregation.DAY: "%Y-%m-%dT00:00:00",
        }
        return func.strftime(formats[aggregation], column)

    @staticmethod
    def _bucket_timestamp(value) -> datetime:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=UTC)
        return datetime.fromisoformat(str(value)).replace(tzinfo=UTC)


def enforce_history_access(user: UserRecord, query: HistoryQuery) -> None:
    if user.role != "student":
        return
    if query.source is not HistorySource.SOLAR:
        raise HistoryAccessError("Detailed history requires staff access")
    if query.aggregation not in {Aggregation.HOUR, Aggregation.DAY}:
        raise HistoryAccessError("Student history requires hour or day aggregation")
    if query.device_id is not None or query.area_id is not None:
        raise HistoryAccessError("Device and area filters require staff access")


class ReportService:
    def __init__(self, session: Session, *, clock=None) -> None:
        self.session = session
        self.history = HistoryService(session)
        self.clock = clock or (lambda: datetime.now(UTC))

    def generate(self, query: ReportQuery, user: UserRecord, *, audit: bool = True) -> TechnicalReport:
        start, end = query.resolved_window(self.clock())
        history_query = HistoryQuery(
            source=query.source, from_=start, to=end, device_id=query.device_id,
            area_id=query.area_id, aggregation=query.aggregation, limit=query.limit,
        )
        enforce_history_access(user, history_query)
        report = TechnicalReport(
            period=query.period, generated_at=self.clock(), from_=start, to=end,
            history=self.history.query(history_query),
        )
        if audit:
            self._audit("report.access", user, query, None)
        return report

    def export_csv(self, report: TechnicalReport, user: UserRecord, query: ReportQuery) -> bytes:
        metric_names = sorted({name for point in report.history.items for name in point.metrics})
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(["timestamp", "source", "device_id", "area_id", "area", *metric_names])
        for point in report.history.items:
            writer.writerow([
                point.timestamp.isoformat(), point.source.value, self._safe_text(point.device_id),
                str(point.area_id) if point.area_id else "", self._safe_text(point.area or ""),
                *(point.metrics.get(name) for name in metric_names),
            ])
        self._audit("report.export", user, query, "csv")
        return output.getvalue().encode("utf-8")

    def export_pdf(self, report: TechnicalReport, user: UserRecord, query: ReportQuery) -> bytes:
        lines = [
            "Smart Renewable Energy Management System",
            f"Technical {report.period.value} report: {report.history.source.value}",
            f"From: {report.from_.isoformat()}", f"To: {report.to.isoformat()}",
            f"Aggregation: {report.history.aggregation.value}",
            f"Records: {report.history.total}", "",
        ]
        for point in report.history.items[:35]:
            metrics = ", ".join(f"{key}={value if value is not None else 'N/A'}" for key, value in point.metrics.items())
            lines.append(f"{point.timestamp.isoformat()} {point.device_id}: {metrics}")
        if report.history.total > 35:
            lines.append("Additional records omitted from PDF summary; use CSV for complete data.")
        self._audit("report.export", user, query, "pdf")
        return self._simple_pdf(lines)

    def _audit(self, category: str, user: UserRecord, query: ReportQuery, export_format: str | None) -> None:
        self.session.add(SystemEventRecord(
            timestamp=self.clock(), category=category, severity="info",
            message="Historical report accessed" if export_format is None else "Historical report exported",
            details={
                "user_id": str(user.id), "source": query.source.value,
                "period": query.period.value, "aggregation": query.aggregation.value,
                "format": export_format,
            },
        ))

    @staticmethod
    def _safe_text(value: str) -> str:
        return f"'{value}" if value.startswith(("=", "+", "-", "@")) else value

    @staticmethod
    def _simple_pdf(lines: list[str]) -> bytes:
        def escape(value: str) -> str:
            return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

        commands = ["BT", "/F1 9 Tf", "40 760 Td"]
        for line in lines:
            commands.extend([f"({escape(line[:110])}) Tj", "0 -14 Td"])
        commands.append("ET")
        stream = "\n".join(commands).encode("latin-1", errors="replace")
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
        ]
        pdf = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for index, obj in enumerate(objects, 1):
            offsets.append(len(pdf))
            pdf.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
        xref = len(pdf)
        pdf.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
        for offset in offsets[1:]:
            pdf.extend(f"{offset:010d} 00000 n \n".encode())
        pdf.extend(f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
        return bytes(pdf)
