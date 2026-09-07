"""Database-only system energy analytics for local calendar-day summaries."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
import math
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.core.config import settings
from apps.models.persistence import InverterReadingRecord, SolarReadingRecord
from apps.schemas.energy_analytics import (
    DailyEnergySummary,
    EnergyCoverageStatus,
    EnergyMetricCoverage,
    EnergyMetricValues,
    EnergySummaryResponse,
)


INSTALLATION_TIMEZONE = "Africa/Lagos"


class EnergyAnalyticsService:
    """Calculate bounded summaries without accessing collectors or hardware."""

    def __init__(
        self,
        session: Session,
        *,
        clock: Callable[[], datetime] | None = None,
        max_integration_gap_seconds: float | None = None,
    ) -> None:
        self.session = session
        self.clock = clock or (lambda: datetime.now(UTC))
        self.timezone = ZoneInfo(INSTALLATION_TIMEZONE)
        self.max_gap_seconds = (
            max_integration_gap_seconds
            if max_integration_gap_seconds is not None
            else settings.energy_max_integration_gap_seconds
        )

    def summarize(self, from_date: date, to_date: date) -> EnergySummaryResponse:
        if from_date > to_date:
            raise ValueError("from must be on or before to")
        if (to_date - from_date).days > 366:
            raise ValueError("Energy summary range cannot exceed 367 days")

        start_local = datetime.combine(from_date, time.min, self.timezone)
        end_local = datetime.combine(to_date + timedelta(days=1), time.min, self.timezone)
        start_utc = start_local.astimezone(UTC)
        end_utc = end_local.astimezone(UTC)
        integration_padding = timedelta(seconds=self.max_gap_seconds)

        solar_rows = self.session.scalars(
            select(SolarReadingRecord)
            .where(SolarReadingRecord.timestamp >= start_utc)
            .where(SolarReadingRecord.timestamp < end_utc)
            .order_by(SolarReadingRecord.timestamp)
        ).all()
        inverter_rows = self.session.scalars(
            select(InverterReadingRecord)
            .where(InverterReadingRecord.timestamp >= start_utc - integration_padding)
            .where(InverterReadingRecord.timestamp < end_utc + integration_padding)
            .order_by(InverterReadingRecord.timestamp)
        ).all()

        solar_by_day: dict[date, list[SolarReadingRecord]] = defaultdict(list)
        inverter_by_day: dict[date, list[InverterReadingRecord]] = defaultdict(list)
        for row in solar_rows:
            solar_by_day[self._local_day(row.timestamp)].append(row)
        for row in inverter_rows:
            inverter_by_day[self._local_day(row.timestamp)].append(row)

        now_local = self._aware(self.clock()).astimezone(self.timezone)
        days: list[DailyEnergySummary] = []
        current = from_date
        while current <= to_date:
            generated, generated_coverage = self._generated_for_day(
                current, solar_by_day[current], now_local
            )
            consumption_rows = (
                inverter_by_day[current - timedelta(days=1)]
                + inverter_by_day[current]
                + inverter_by_day[current + timedelta(days=1)]
            )
            consumed, consumption_coverage = self._consumed_for_day(
                current, consumption_rows, now_local
            )
            # Siseli GridPower is persisted verbatim, but this repository has no
            # verified import/export sign convention. Never label it as import.
            grid_imported = None
            grid_coverage = EnergyCoverageStatus.UNAVAILABLE
            coverage = EnergyMetricCoverage(
                generated=generated_coverage,
                consumption=consumption_coverage,
                grid_import=grid_coverage,
            )
            days.append(DailyEnergySummary(
                date=current,
                generated_kwh=generated,
                consumed_kwh=consumed,
                grid_imported_kwh=grid_imported,
                status=self._overall_status(coverage),
                coverage=coverage,
            ))
            current += timedelta(days=1)

        total_coverage = EnergyMetricCoverage(
            generated=self._range_coverage(days, "generated_kwh", "generated"),
            consumption=self._range_coverage(days, "consumed_kwh", "consumption"),
            grid_import=self._range_coverage(days, "grid_imported_kwh", "grid_import"),
        )
        return EnergySummaryResponse(
            timezone=INSTALLATION_TIMEZONE,
            from_=from_date,
            to=to_date,
            totals=EnergyMetricValues(
                generated_kwh=self._known_sum(day.generated_kwh for day in days),
                consumed_kwh=self._known_sum(day.consumed_kwh for day in days),
                grid_imported_kwh=self._known_sum(day.grid_imported_kwh for day in days),
            ),
            status=self._overall_status(total_coverage),
            coverage=total_coverage,
            days=days,
        )

    def _generated_for_day(
        self,
        day: date,
        rows: list[SolarReadingRecord],
        now_local: datetime,
    ) -> tuple[float | None, EnergyCoverageStatus]:
        valid = [row for row in rows if row.daily_energy_kwh is not None]
        if not valid:
            return None, EnergyCoverageStatus.UNAVAILABLE
        value = max(float(row.daily_energy_kwh) for row in valid)
        latest = max(self._aware(row.timestamp).astimezone(self.timezone) for row in valid)
        return value, self._sample_coverage(day, latest, now_local)

    def _consumed_for_day(
        self,
        day: date,
        rows: list[InverterReadingRecord],
        now_local: datetime,
    ) -> tuple[float | None, EnergyCoverageStatus]:
        by_device: dict[object, list[InverterReadingRecord]] = defaultdict(list)
        for row in rows:
            by_device[row.device_id].append(row)

        energy_wh = 0.0
        valid_intervals = 0
        skipped_gap = False
        first_timestamp: datetime | None = None
        last_timestamp: datetime | None = None
        day_start = datetime.combine(day, time.min, self.timezone).astimezone(UTC)
        day_end = datetime.combine(day + timedelta(days=1), time.min, self.timezone).astimezone(UTC)
        for device_rows in by_device.values():
            # Siseli may return one unchanged source sample through several polls.
            # Persistence can therefore contain duplicate source timestamps.
            samples: dict[datetime, float | None] = {}
            for row in device_rows:
                timestamp = self._aware(row.timestamp)
                if timestamp not in samples or row.output_power_w is not None:
                    samples[timestamp] = row.output_power_w
            ordered = sorted(samples.items())
            for (left_time, left_value), (right_time, right_value) in zip(ordered, ordered[1:]):
                gap_seconds = (right_time - left_time).total_seconds()
                if gap_seconds <= 0:
                    continue
                interval_start = max(left_time, day_start)
                interval_end = min(right_time, day_end)
                if interval_start >= interval_end:
                    continue
                if gap_seconds > self.max_gap_seconds:
                    skipped_gap = True
                    continue
                if left_value is None or right_value is None:
                    skipped_gap = True
                    continue
                left_power = float(left_value)
                right_power = float(right_value)
                if (
                    not math.isfinite(left_power)
                    or not math.isfinite(right_power)
                    or left_power < 0
                    or right_power < 0
                ):
                    skipped_gap = True
                    continue
                start_ratio = (interval_start - left_time).total_seconds() / gap_seconds
                end_ratio = (interval_end - left_time).total_seconds() / gap_seconds
                start_power = left_power + (right_power - left_power) * start_ratio
                end_power = left_power + (right_power - left_power) * end_ratio
                interval_seconds = (interval_end - interval_start).total_seconds()
                energy_wh += ((start_power + end_power) / 2.0) * (interval_seconds / 3600.0)
                valid_intervals += 1
                first_timestamp = min(first_timestamp, interval_start) if first_timestamp else interval_start
                last_timestamp = max(last_timestamp, interval_end) if last_timestamp else interval_end

        if valid_intervals == 0:
            return None, EnergyCoverageStatus.UNAVAILABLE

        coverage = self._interval_coverage(
            day, first_timestamp, last_timestamp, now_local, skipped_gap
        )
        return energy_wh / 1000.0, coverage

    def _sample_coverage(
        self, day: date, latest: datetime, now_local: datetime
    ) -> EnergyCoverageStatus:
        if day >= now_local.date():
            return EnergyCoverageStatus.PARTIAL
        day_end = datetime.combine(day + timedelta(days=1), time.min, self.timezone)
        if (day_end - latest).total_seconds() <= self.max_gap_seconds:
            return EnergyCoverageStatus.COMPLETE
        return EnergyCoverageStatus.PARTIAL

    def _interval_coverage(
        self,
        day: date,
        first: datetime,
        last: datetime,
        now_local: datetime,
        skipped_gap: bool,
    ) -> EnergyCoverageStatus:
        if skipped_gap or day >= now_local.date():
            return EnergyCoverageStatus.PARTIAL
        start = datetime.combine(day, time.min, self.timezone).astimezone(UTC)
        end = datetime.combine(day + timedelta(days=1), time.min, self.timezone).astimezone(UTC)
        if (
            (first - start).total_seconds() <= self.max_gap_seconds
            and (end - last).total_seconds() <= self.max_gap_seconds
        ):
            return EnergyCoverageStatus.COMPLETE
        return EnergyCoverageStatus.PARTIAL

    def _local_day(self, value: datetime) -> date:
        return self._aware(value).astimezone(self.timezone).date()

    @staticmethod
    def _aware(value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)

    @staticmethod
    def _known_sum(values) -> float | None:
        known = [float(value) for value in values if value is not None]
        return sum(known) if known else None

    @staticmethod
    def _overall_status(coverage: EnergyMetricCoverage) -> EnergyCoverageStatus:
        values = (coverage.generated, coverage.consumption, coverage.grid_import)
        if all(value is EnergyCoverageStatus.UNAVAILABLE for value in values):
            return EnergyCoverageStatus.UNAVAILABLE
        if all(value is EnergyCoverageStatus.COMPLETE for value in values):
            return EnergyCoverageStatus.COMPLETE
        return EnergyCoverageStatus.PARTIAL

    @staticmethod
    def _range_coverage(
        days: list[DailyEnergySummary], metric: str, coverage_key: str
    ) -> EnergyCoverageStatus:
        states = [getattr(day.coverage, coverage_key) for day in days]
        values = [getattr(day, metric) for day in days]
        if not any(value is not None for value in values):
            return EnergyCoverageStatus.UNAVAILABLE
        if all(state is EnergyCoverageStatus.COMPLETE for state in states):
            return EnergyCoverageStatus.COMPLETE
        return EnergyCoverageStatus.PARTIAL
