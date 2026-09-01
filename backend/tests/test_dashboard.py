"""Collector-first dashboard aggregation and partial-outage tests."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.integrations.inverter import InverterAdapter, MockBeveClient
from apps.jobs.energy_collector import CollectorSnapshot, DeviceCollectionState
from apps.models import BreakerDevice, BreakerStatus, DeviceCapability, DeviceStatus
from apps.models.persistence import (
    AlertRecord, AreaRecord, BatteryReadingRecord, BreakerReadingRecord,
    DeviceRecord, GridReadingRecord, InverterReadingRecord, SolarReadingRecord,
)
from apps.services.dashboard_service import DashboardService
from apps.api.dashboard import get_dashboard_service
from apps.core.permissions import require_student
from apps.main import app
from apps.schemas.dashboard import DashboardArea, DashboardAreas, DashboardSnapshot, DashboardSystem, OverallHealth


NOW = datetime(2026, 9, 1, 12, 20, tzinfo=UTC)


class FakeCollector:
    def __init__(self, snapshot: CollectorSnapshot) -> None:
        self.snapshot = snapshot
        self.calls = 0

    async def get_snapshot(self) -> CollectorSnapshot:
        self.calls += 1
        return self.snapshot.model_copy(deep=True)


@pytest.fixture
def dashboard_db():
    engine = create_engine("sqlite:///:memory:")
    from apps.db.base import Base

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def breaker(device_id: str, area: str, *, online: bool, seen: datetime | None, power: float | None):
    return BreakerDevice(
        id=device_id, friendly_name=f"{area} breaker", area=area,
        online=online, last_seen=seen, capabilities=DeviceCapability(),
        status=BreakerStatus(
            device_id=device_id,
            status=DeviceStatus.ONLINE if online else DeviceStatus.OFFLINE,
            switch_on=True if online else None,
            electrical={"voltage_volts": 0 if online else None, "current_amperes": 0 if online else None, "active_power_watts": power},
            energy={"total_kwh": 0 if online else None},
        ),
    )


@pytest.mark.asyncio
async def test_dashboard_aggregates_one_collector_snapshot_and_retains_zero(dashboard_db) -> None:
    inverter = InverterAdapter().read(MockBeveClient())
    snapshot = CollectorSnapshot(
        inverter=inverter,
        breakers={
            "library": breaker("library", "Library", online=True, seen=NOW, power=0),
            "admin": breaker("admin", "Admin offices", online=False, seen=None, power=None),
        },
        devices={
            "inverter": DeviceCollectionState(device_id="inverter", online=True, stale=False, last_seen=NOW),
            "library": DeviceCollectionState(device_id="library", online=True, stale=False, last_seen=NOW),
            "admin": DeviceCollectionState(device_id="admin", online=False, stale=True, last_seen=None),
        },
    )
    collector = FakeCollector(snapshot)
    with dashboard_db() as session:
        session.add(AlertRecord(timestamp=NOW, severity="warning", title="Active", message="test", active=True))
        session.commit()
        result = await DashboardService(session, collector, clock=lambda: NOW).get_dashboard()

    assert collector.calls == 1
    assert result.inverter.status == "Battery Mode"
    assert result.solar.pv1_power_w == 0
    assert result.grid.voltage == 0
    assert result.areas[1].area == "Library"
    assert result.areas[1].voltage_v == 0
    assert result.areas[1].power_w == 0
    assert result.system.online_devices == 2
    assert result.system.offline_devices == 1
    assert result.system.stale_devices == 1
    assert result.system.active_alerts == 1
    assert result.system.overall_health.value == "degraded"


@pytest.mark.asyncio
async def test_partial_breaker_outage_keeps_other_area_and_last_known_inverter(dashboard_db) -> None:
    inverter = InverterAdapter().read(MockBeveClient())
    snapshot = CollectorSnapshot(
        inverter=inverter,
        breakers={
            "library": breaker("library", "Library", online=True, seen=NOW, power=125),
            "admin": breaker("admin", "Admin offices", online=False, seen=NOW - timedelta(minutes=5), power=None),
        },
        devices={
            "inverter": DeviceCollectionState(device_id="inverter", online=False, stale=False, last_seen=NOW),
            "library": DeviceCollectionState(device_id="library", online=True, stale=False, last_seen=NOW),
            "admin": DeviceCollectionState(device_id="admin", online=False, stale=True, last_seen=NOW - timedelta(minutes=5)),
        },
    )
    with dashboard_db() as session:
        result = await DashboardService(session, FakeCollector(snapshot), clock=lambda: NOW).get_dashboard()

    assert result.inverter.output_power_w == 12
    assert next(area for area in result.areas if area.area == "Library").power_w == 125
    assert next(area for area in result.areas if area.area == "Admin offices").online is False
    assert result.system.offline_devices == 2


@pytest.mark.asyncio
async def test_database_fallback_returns_latest_normalized_state_without_collector(dashboard_db) -> None:
    with dashboard_db() as session:
        area = AreaRecord(name="Library")
        inverter_device = DeviceRecord(external_reference="inverter-db", friendly_name="Inverter", device_type="inverter", last_seen=NOW)
        breaker_device = DeviceRecord(external_reference="breaker-db", friendly_name="Breaker", device_type="breaker", area=area, last_seen=NOW)
        session.add_all([area, inverter_device, breaker_device])
        session.flush()
        session.add_all([
            InverterReadingRecord(timestamp=NOW, device_id=inverter_device.id, status="Battery Mode", output_power_w=0),
            BatteryReadingRecord(timestamp=NOW, device_id=inverter_device.id, soc=100, charging_current=0),
            SolarReadingRecord(timestamp=NOW, device_id=inverter_device.id, connected="PV Not Connected", total_power_w=0),
            GridReadingRecord(timestamp=NOW, device_id=inverter_device.id, voltage=0, frequency=0, power_w=0),
            BreakerReadingRecord(timestamp=NOW, device_id=breaker_device.id, online=True, switch_state=False, voltage_v=0, current_a=0, power_w=0, accumulated_energy=None),
        ])
        session.commit()
        result = await DashboardService(session, None, clock=lambda: NOW).get_dashboard()

    assert result.inverter.output_power_w == 0
    assert result.battery.charging_current == 0
    assert result.grid.frequency == 0
    assert result.areas[0].is_on is False
    assert result.areas[0].accumulated_energy is None
    assert result.system.overall_health.value == "healthy"


def test_dashboard_routes_expose_snapshot_summary_and_areas(client) -> None:
    system = DashboardSystem(
        overall_health=OverallHealth.HEALTHY, last_update=NOW,
        online_devices=1, offline_devices=0, stale_devices=0, active_alerts=0,
    )
    area = DashboardArea(
        device_id="library", area="Library", online=True, is_on=True,
        voltage_v=0, current_a=0, power_w=0, accumulated_energy=None, last_seen=NOW,
    )

    class StubDashboardService:
        async def get_dashboard(self):
            return DashboardSnapshot(system=system, areas=[area])

        async def get_summary(self):
            return system

        async def get_areas(self):
            return DashboardAreas(last_update=NOW, items=[area], total=1)

    app.dependency_overrides[require_student] = lambda: None
    app.dependency_overrides[get_dashboard_service] = StubDashboardService
    try:
        snapshot = client.get("/api/v1/dashboard")
        summary = client.get("/api/v1/dashboard/summary")
        areas = client.get("/api/v1/dashboard/areas")
    finally:
        app.dependency_overrides.clear()

    assert snapshot.status_code == summary.status_code == areas.status_code == 200
    assert snapshot.json()["areas"][0]["voltage_v"] == 0
    assert summary.json()["overall_health"] == "healthy"
    assert areas.json()["total"] == 1
