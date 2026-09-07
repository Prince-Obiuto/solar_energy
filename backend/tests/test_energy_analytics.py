"""Database-only energy analytics and aggregate API tests."""

from datetime import UTC, date, datetime, timedelta
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.core.security import create_access_token, hash_password
from apps.db.base import Base
from apps.db.session import get_db
from apps.main import app
from apps.models.persistence import (
    DeviceRecord,
    GridReadingRecord,
    InverterReadingRecord,
    SolarReadingRecord,
    UserRecord,
)
from apps.services.energy_analytics_service import EnergyAnalyticsService


DAY = date(2026, 9, 1)
# Africa/Lagos local midnight is 23:00 UTC on the preceding date.
DAY_START = datetime(2026, 8, 31, 23, 0, tzinfo=UTC)


@pytest.fixture
def analytics_db():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        device = DeviceRecord(
            external_reference="analytics-inverter",
            friendly_name="Inverter",
            device_type="inverter",
        )
        session.add(device)
        session.commit()
        device_id = device.id
    try:
        yield factory, device_id
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def service(session, *, max_gap=3600):
    return EnergyAnalyticsService(
        session,
        clock=lambda: datetime(2026, 9, 8, tzinfo=UTC),
        max_integration_gap_seconds=max_gap,
    )


def test_solar_uses_daily_cumulative_maximum_not_sum(analytics_db) -> None:
    factory, device_id = analytics_db
    with factory() as session:
        for minutes, value in ((5, 0.5), (10, 1.0), (15, 2.5)):
            session.add(SolarReadingRecord(
                timestamp=DAY_START + timedelta(minutes=minutes),
                device_id=device_id,
                daily_energy_kwh=value,
            ))
        session.commit()
        result = service(session).summarize(DAY, DAY)

    assert result.days[0].generated_kwh == 2.5
    assert result.totals.generated_kwh == 2.5


def test_confirmed_solar_zero_is_not_unavailable(analytics_db) -> None:
    factory, device_id = analytics_db
    with factory() as session:
        session.add(SolarReadingRecord(
            timestamp=DAY_START + timedelta(hours=23, minutes=55),
            device_id=device_id,
            daily_energy_kwh=0,
        ))
        session.commit()
        result = service(session).summarize(DAY, DAY)

    assert result.days[0].generated_kwh == 0
    assert result.days[0].coverage.generated.value == "complete"


def test_no_solar_data_returns_null(analytics_db) -> None:
    factory, _ = analytics_db
    with factory() as session:
        result = service(session).summarize(DAY, DAY)
    assert result.days[0].generated_kwh is None
    assert result.days[0].coverage.generated.value == "unavailable"


def test_consumption_uses_trapezoidal_power_integration(analytics_db) -> None:
    factory, device_id = analytics_db
    with factory() as session:
        session.add_all([
            InverterReadingRecord(
                timestamp=DAY_START,
                device_id=device_id,
                output_power_w=1000,
            ),
            InverterReadingRecord(
                timestamp=DAY_START + timedelta(hours=1),
                device_id=device_id,
                output_power_w=2000,
            ),
        ])
        session.commit()
        result = service(session).summarize(DAY, DAY)

    assert result.days[0].consumed_kwh == pytest.approx(1.5)


def test_integration_skips_excessive_gap_and_marks_partial(analytics_db) -> None:
    factory, device_id = analytics_db
    with factory() as session:
        session.add_all([
            InverterReadingRecord(timestamp=DAY_START, device_id=device_id, output_power_w=1000),
            InverterReadingRecord(timestamp=DAY_START + timedelta(minutes=5), device_id=device_id, output_power_w=1000),
            InverterReadingRecord(timestamp=DAY_START + timedelta(hours=12), device_id=device_id, output_power_w=1000),
        ])
        session.commit()
        result = service(session, max_gap=600).summarize(DAY, DAY)

    assert result.days[0].consumed_kwh == pytest.approx(1 / 12)
    assert result.days[0].coverage.consumption.value == "partial"
    assert result.status.value == "partial"


def test_only_excessive_gap_does_not_invent_zero_energy(analytics_db) -> None:
    factory, device_id = analytics_db
    with factory() as session:
        session.add_all([
            InverterReadingRecord(timestamp=DAY_START, device_id=device_id, output_power_w=0),
            InverterReadingRecord(timestamp=DAY_START + timedelta(hours=12), device_id=device_id, output_power_w=0),
        ])
        session.commit()
        result = service(session, max_gap=600).summarize(DAY, DAY)

    assert result.days[0].consumed_kwh is None
    assert result.days[0].coverage.consumption.value == "unavailable"


def test_lagos_midnight_boundary_and_multiple_day_totals(analytics_db) -> None:
    factory, device_id = analytics_db
    with factory() as session:
        session.add_all([
            SolarReadingRecord(
                timestamp=datetime(2026, 9, 1, 22, 30, tzinfo=UTC),
                device_id=device_id,
                daily_energy_kwh=2,
            ),
            SolarReadingRecord(
                timestamp=datetime(2026, 9, 1, 23, 30, tzinfo=UTC),
                device_id=device_id,
                daily_energy_kwh=0.5,
            ),
        ])
        session.commit()
        result = service(session).summarize(DAY, DAY + timedelta(days=1))

    assert [item.generated_kwh for item in result.days] == [2, 0.5]
    assert result.totals.generated_kwh == 2.5


def test_consumption_interval_is_split_at_lagos_midnight(analytics_db) -> None:
    factory, device_id = analytics_db
    with factory() as session:
        session.add_all([
            InverterReadingRecord(
                timestamp=datetime(2026, 9, 1, 22, 55, tzinfo=UTC),
                device_id=device_id,
                output_power_w=1000,
            ),
            InverterReadingRecord(
                timestamp=datetime(2026, 9, 1, 23, 5, tzinfo=UTC),
                device_id=device_id,
                output_power_w=1000,
            ),
        ])
        session.commit()
        result = service(session, max_gap=900).summarize(DAY, DAY + timedelta(days=1))

    assert result.days[0].consumed_kwh == pytest.approx(1 / 12)
    assert result.days[1].consumed_kwh == pytest.approx(1 / 12)
    assert result.totals.consumed_kwh == pytest.approx(1 / 6)


def test_grid_import_remains_unavailable_without_verified_direction(analytics_db) -> None:
    factory, device_id = analytics_db
    with factory() as session:
        session.add_all([
            GridReadingRecord(timestamp=DAY_START, device_id=device_id, power_w=500),
            GridReadingRecord(timestamp=DAY_START + timedelta(minutes=5), device_id=device_id, power_w=-500),
        ])
        session.commit()
        result = service(session).summarize(DAY, DAY)

    assert result.days[0].grid_imported_kwh is None
    assert result.coverage.grid_import.value == "unavailable"


def test_student_can_access_summary_without_hardware_calls(analytics_db, monkeypatch, client) -> None:
    factory, device_id = analytics_db
    with factory() as session:
        user = UserRecord(
            id=uuid.uuid4(),
            email="student.analytics@example.test",
            password_hash=hash_password("correct horse battery staple"),
            role="student",
            is_active=True,
        )
        session.add_all([
            user,
            SolarReadingRecord(timestamp=DAY_START, device_id=device_id, daily_energy_kwh=0),
        ])
        session.commit()
        user_id = user.id

    def override_db():
        with factory() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    def hardware_access_would_fail():
        raise AssertionError("summary endpoint must not access hardware")

    monkeypatch.setattr("apps.api.energy.get_energy_collector", hardware_access_would_fail)
    token, _ = create_access_token(str(user_id))
    app.dependency_overrides[get_db] = override_db
    try:
        response = client.get(
            "/api/v1/energy/summary",
            params={"from": DAY.isoformat(), "to": DAY.isoformat()},
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["days"][0]["generated_kwh"] == 0
    assert response.json()["days"][0]["grid_imported_kwh"] is None
