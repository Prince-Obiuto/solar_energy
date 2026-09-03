"""Regression tests proving monitoring APIs never initiate TinyTuya traffic."""

from datetime import UTC, datetime

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.breakers import list_breakers
from apps.db.base import Base
from apps.integrations.tuya.client import TuyaDeviceConfig
from apps.jobs.energy_collector import CollectorSnapshot, DeviceCollectionState
from apps.models import (
    BreakerDevice, BreakerStatus, DataFreshness, DeviceCapability, DeviceStatus, SourceStatus,
)
from apps.models.persistence import BreakerReadingRecord, DeviceRecord
from apps.services.breaker_monitoring_service import BreakerMonitoringService
from apps.services.breaker_service import BreakerRegistration, BreakerService


class CountingClient:
    def __init__(self):
        self.calls = 0
        self.config = TuyaDeviceConfig(
            device_id="cache-breaker", friendly_name="Cached breaker", area="Library",
            local_key=SecretStr("test-only-key"), ip_address="192.0.2.44", protocol_version="3.5",
        )

    def read_status(self):
        self.calls += 1
        return {"dps": {"1": True}}


class SnapshotSource:
    def __init__(self, snapshot):
        self.snapshot = snapshot

    async def get_snapshot(self):
        return self.snapshot.model_copy(deep=True)


def setup():
    engine = create_engine("sqlite+pysqlite://", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    client = CountingClient()
    breakers = BreakerService([BreakerRegistration(client, DeviceCapability(
        switching=True, voltage=True, current=True, instantaneous_power=True,
    ))])
    return factory, client, breakers


@pytest.mark.asyncio
async def test_cached_breaker_reads_never_touch_hardware(monkeypatch) -> None:
    factory, client, breakers = setup()
    now = datetime(2026, 9, 3, tzinfo=UTC)
    breaker = BreakerDevice(
        id="cache-breaker", friendly_name="Cached breaker", area="Library", online=True,
        last_seen=now, capabilities=breakers.get_capabilities("cache-breaker"),
        status=BreakerStatus(device_id="cache-breaker", name="Cached breaker",
                             status=DeviceStatus.ONLINE, switch_on=True),
    )
    snapshot = CollectorSnapshot(
        breakers={"cache-breaker": breaker},
        devices={"cache-breaker": DeviceCollectionState(
            device_id="cache-breaker", online=True, stale=False,
            last_seen=now, last_successful_update=now,
            source_status=SourceStatus.CONNECTED, data_freshness=DataFreshness.LIVE,
        )},
    )
    source = SnapshotSource(snapshot)
    import apps.jobs.energy_collector as collector_module
    monkeypatch.setattr(collector_module, "get_energy_collector", lambda: source)
    with factory() as session:
        for _ in range(10):
            response = await list_breakers(session=session, service=breakers)
            assert response["items"][0].status.switch_on is True
    assert client.calls == 0


@pytest.mark.asyncio
async def test_persistence_fallback_and_offline_snapshot_are_non_blocking() -> None:
    factory, client, breakers = setup()
    now = datetime.now(UTC)
    with factory.begin() as session:
        device = DeviceRecord(
            external_reference="cache-breaker", friendly_name="Cached breaker",
            device_type="breaker",
        )
        session.add(device)
        session.flush()
        session.add(BreakerReadingRecord(
            timestamp=now, device_id=device.id, online=True, switch_state=False,
            voltage_v=230, current_a=0, power_w=0, accumulated_energy=0,
        ))
    with factory() as session:
        result = await BreakerMonitoringService(session, breakers, None).list_breakers()
        assert result[0].online is True and result[0].status.switch_on is False
        assert result[0].status.electrical.current_amperes == 0
    offline = CollectorSnapshot(
        breakers={"cache-breaker": breakers.describe_breaker("cache-breaker")},
        devices={"cache-breaker": DeviceCollectionState(
            device_id="cache-breaker", online=False, stale=True,
            source_status=SourceStatus.UNREACHABLE, data_freshness=DataFreshness.STALE,
        )},
    )
    with factory() as session:
        result = await BreakerMonitoringService(session, breakers, SnapshotSource(offline)).list_breakers()
        assert result[0].online is False and result[0].data_status.stale is True
    assert client.calls == 0
