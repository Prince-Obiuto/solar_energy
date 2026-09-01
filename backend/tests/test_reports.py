"""Historical queries, aggregation, RBAC, CSV/PDF, and access-audit tests."""

from datetime import UTC, datetime, timedelta
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.core.security import create_access_token, hash_password
from apps.db.base import Base
from apps.db.session import get_db
from apps.main import app
from apps.models import UserRole
from apps.models.persistence import (
    AreaRecord, BatteryReadingRecord, BreakerReadingRecord, DeviceRecord,
    GridReadingRecord, InverterReadingRecord, SolarReadingRecord,
    SystemEventRecord, UserRecord,
)
from apps.schemas.report import Aggregation, HistoryQuery, HistorySource, ReportPeriod, ReportQuery
from apps.services.report_service import HistoryService, ReportService


START = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)


@pytest.fixture
def report_context():
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    users = {}
    with factory() as session:
        area = AreaRecord(name="Library")
        inverter = DeviceRecord(external_reference="inverter-report", friendly_name="Inverter", device_type="inverter")
        breaker = DeviceRecord(external_reference="breaker-report", friendly_name="Library breaker", device_type="breaker", area=area)
        session.add_all([area, inverter, breaker])
        session.flush()
        for offset, power in ((0, 0.0), (30, 100.0)):
            timestamp = START + timedelta(minutes=offset)
            session.add_all([
                InverterReadingRecord(timestamp=timestamp, device_id=inverter.id, status="Battery Mode", output_power_w=power, output_voltage=220, output_frequency=50, load_percentage=0),
                BatteryReadingRecord(timestamp=timestamp, device_id=inverter.id, soc=100, voltage=53.4, power_w=power, charging_current=0, discharge_current=1, status="Discharging"),
                SolarReadingRecord(timestamp=timestamp, device_id=inverter.id, connected="PV Not Connected", total_power_w=power, daily_energy_kwh=offset / 30, monthly_energy_kwh=2, total_energy_kwh=8),
                GridReadingRecord(timestamp=timestamp, device_id=inverter.id, voltage=0, frequency=0, power_w=0),
                BreakerReadingRecord(timestamp=timestamp, device_id=breaker.id, online=True, switch_state=offset == 0, voltage_v=195, current_a=0, power_w=power, accumulated_energy=12 + offset / 30),
            ])
        for role in UserRole:
            user = UserRecord(
                id=uuid.uuid4(), email=f"{role.value}.reports@example.test",
                password_hash=hash_password("correct horse battery staple"), role=role.value, is_active=True,
            )
            session.add(user)
            users[role] = user
        session.commit()
        area_id = area.id

    def override_db():
        with factory() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            yield client, factory, users, area_id
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def auth(user):
    token, _ = create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("source", list(HistorySource))
def test_raw_history_exposes_only_verified_normalized_metrics(report_context, source) -> None:
    _, factory, _, _ = report_context
    with factory() as session:
        result = HistoryService(session).query(HistoryQuery(source=source, aggregation=Aggregation.RAW))
    assert result.total == 2
    assert result.items[0].timestamp.tzinfo is not None
    metrics = result.items[0].metrics
    assert 0 in metrics.values() or 0.0 in metrics.values()
    if source is HistorySource.AREAS:
        assert "accumulated_energy" in metrics
        assert "total_energy_kwh" not in metrics
    if source is HistorySource.GRID:
        assert metrics["available"] is False


def test_hour_aggregation_averages_power_and_uses_maximum_counter(report_context) -> None:
    _, factory, _, _ = report_context
    with factory() as session:
        solar = HistoryService(session).query(HistoryQuery(source="solar", aggregation="hour"))
        areas = HistoryService(session).query(HistoryQuery(source="areas", aggregation="hour"))
    assert solar.total == 1
    assert solar.items[0].metrics["power_w"] == 50
    assert solar.items[0].metrics["daily_energy_kwh"] == 1
    assert solar.items[0].metrics["connected"] is None
    assert areas.items[0].metrics["accumulated_energy"] == 13
    assert areas.items[0].metrics["breaker_state"] is None


def test_filters_and_limit_are_applied(report_context) -> None:
    _, factory, _, area_id = report_context
    with factory() as session:
        result = HistoryService(session).query(HistoryQuery(
            source="areas", from_=START + timedelta(minutes=1), to=START + timedelta(hours=1),
            device_id="breaker-report", area_id=area_id, aggregation="raw", limit=1,
        ))
    assert result.total == 1
    assert result.items[0].timestamp == START + timedelta(minutes=30)


def test_report_periods_and_exports_are_audited(report_context) -> None:
    _, factory, users, _ = report_context
    query = ReportQuery(
        source="areas", period=ReportPeriod.CUSTOM, from_=START,
        to=START + timedelta(hours=1), aggregation="raw",
    )
    with factory() as session:
        service = ReportService(session, clock=lambda: START + timedelta(hours=1))
        report = service.generate(query, users[UserRole.ADMIN])
        csv_bytes = service.export_csv(report, users[UserRole.ADMIN], query)
        pdf_bytes = service.export_pdf(report, users[UserRole.ADMIN], query)
        session.commit()
        events = session.scalars(select(SystemEventRecord).where(SystemEventRecord.category.in_(["report.access", "report.export"]))).all()

    csv_text = csv_bytes.decode()
    assert "timestamp" in csv_text and START.isoformat() in csv_text
    assert "voltage_v" in csv_text and "accumulated_energy" in csv_text
    assert "accumulated_energy_kwh" not in csv_text
    assert pdf_bytes.startswith(b"%PDF-1.4") and b"Technical custom report" in pdf_bytes
    assert len(events) == 3
    assert all(event.details["user_id"] == str(users[UserRole.ADMIN].id) for event in events)


def test_student_history_is_bounded_while_staff_can_query_details(report_context) -> None:
    client, _, users, _ = report_context
    student = auth(users[UserRole.STUDENT])
    staff = auth(users[UserRole.STAFF])
    assert client.get("/api/v1/energy/history?source=solar&aggregation=hour", headers=student).status_code == 200
    assert client.get("/api/v1/energy/history?source=areas&aggregation=hour", headers=student).status_code == 403
    assert client.get("/api/v1/energy/history?source=solar&aggregation=raw", headers=student).status_code == 403
    response = client.get("/api/v1/energy/history?source=areas&aggregation=raw", headers=staff)
    assert response.status_code == 200
    assert response.json()["items"][0]["metrics"]["accumulated_energy"] == 12


def test_report_csv_pdf_endpoints_and_custom_validation(report_context) -> None:
    client, factory, users, _ = report_context
    headers = auth(users[UserRole.STAFF])
    window = {"period": "custom", "source": "areas", "aggregation": "hour", "from": START.isoformat(), "to": (START + timedelta(hours=1)).isoformat()}
    csv_response = client.get("/api/v1/reports/export.csv", params=window, headers=headers)
    pdf_response = client.get("/api/v1/reports/export.pdf", params=window, headers=headers)
    invalid = client.get("/api/v1/reports?period=custom&source=solar&aggregation=hour", headers=headers)
    assert csv_response.status_code == 200 and csv_response.headers["content-type"].startswith("text/csv")
    assert pdf_response.status_code == 200 and pdf_response.headers["content-type"] == "application/pdf"
    assert invalid.status_code == 422
    with factory() as session:
        assert len(session.scalars(select(SystemEventRecord).where(SystemEventRecord.category == "report.export")).all()) == 2
