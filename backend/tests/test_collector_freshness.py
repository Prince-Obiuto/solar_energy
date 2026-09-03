"""Regression coverage for repeated Siseli samples and monotonic poll cadence."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest

from apps.integrations.inverter import VERIFIED_BEVE_RESPONSE
from apps.jobs.energy_collector import CollectorConfig, EnergyCollector, NullEventPublisher
from apps.models import DataFreshness, SourceStatus
from apps.services.breaker_service import BreakerService
from apps.services.inverter_service import InverterService


class Clock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


class Responses:
    def __init__(self, values):
        self.values = values
        self.index = 0

    def fetch_current_telemetry(self):
        value = self.values[min(self.index, len(self.values) - 1)]
        self.index += 1
        return deepcopy(value)


class Persistence:
    def __init__(self):
        self.timestamps = []

    def persist_inverter(self, _device, telemetry):
        self.timestamps.append(telemetry.timestamp)

    def persist_breaker(self, *_args):
        raise AssertionError("No breaker persistence expected")


def config():
    return CollectorConfig(
        beve_poll_interval_seconds=30, beve_poll_stale_after_seconds=90,
        beve_source_stale_after_seconds=900, tuya_poll_interval_seconds=10,
        telemetry_persist_interval_seconds=1, device_stale_after_seconds=90,
        retry_attempts=1, retry_delay_seconds=0,
    )


@pytest.mark.asyncio
async def test_repeated_source_sample_keeps_cloud_connected_but_source_ages() -> None:
    source_time = datetime(2026, 9, 1, 10, 2, 49, tzinfo=UTC)
    repeated = deepcopy(VERIFIED_BEVE_RESPONSE)
    repeated["timestamp"] = source_time.isoformat().replace("+00:00", "Z")
    advanced = deepcopy(repeated)
    advanced_time = source_time + timedelta(minutes=20)
    advanced["timestamp"] = advanced_time.isoformat().replace("+00:00", "Z")
    clock = Clock(source_time + timedelta(minutes=8))
    persistence = Persistence()
    collector = EnergyCollector(
        InverterService(Responses([repeated, repeated, repeated, repeated, advanced])),
        BreakerService([]), inverter_device_reference="inverter-test",
        config=config(), persistence=persistence, publisher=NullEventPublisher(), clock=clock,
    )
    async def inline(operation, *args):
        return operation(*args)
    collector._run_sync = inline

    successful_polls = []
    for _ in range(3):
        assert await collector.collect_inverter_once() is True
        state = (await collector.get_snapshot()).devices["inverter-test"]
        successful_polls.append(state.last_successful_poll_at)
        assert state.source_timestamp == source_time
        assert state.source_status is SourceStatus.CONNECTED
        clock.now += timedelta(seconds=30)
    assert successful_polls[0] < successful_polls[1] < successful_polls[2]
    assert persistence.timestamps == [source_time]

    clock.now = source_time + timedelta(seconds=901)
    assert await collector.collect_inverter_once() is True
    stale = (await collector.get_snapshot()).devices["inverter-test"]
    assert stale.source_status is SourceStatus.CONNECTED
    assert stale.data_freshness is DataFreshness.STALE
    assert stale.source_age_seconds == 901

    clock.now = advanced_time
    assert await collector.collect_inverter_once() is True
    final_snapshot = await collector.get_snapshot()
    fresh = final_snapshot.devices["inverter-test"]
    assert fresh.source_changed is True
    assert fresh.source_timestamp == advanced_time
    assert fresh.data_freshness is DataFreshness.LIVE
    assert persistence.timestamps == [source_time, advanced_time]
    assert final_snapshot.inverter.grid.voltage == 0
    assert final_snapshot.inverter.solar.pv1_power_w == 0


@pytest.mark.asyncio
async def test_poll_loop_uses_start_to_start_monotonic_cadence_without_overlap() -> None:
    monotonic_now = [0.0]
    starts = []
    durations = iter((8.0, 0.4, 0.4))

    async def sleep(delay):
        monotonic_now[0] += delay

    collector = EnergyCollector(
        InverterService(None), BreakerService([]), inverter_device_reference=None,
        config=config(), publisher=NullEventPublisher(), sleep=sleep,
        monotonic=lambda: monotonic_now[0],
    )
    collector._running = True

    async def collect():
        starts.append(monotonic_now[0])
        monotonic_now[0] += next(durations)
        if len(starts) == 3:
            collector._running = False
        return True

    await collector._poll_loop("source", 30, collect)
    assert starts == [0.0, 30.0, 60.0]
