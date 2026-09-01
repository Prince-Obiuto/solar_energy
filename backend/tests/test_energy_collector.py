"""Deterministic, network-free tests for the telemetry collection engine."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import threading
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient

from apps.integrations.inverter import (
    BeveConnectionError,
    BeveTimeoutError,
    VERIFIED_BEVE_RESPONSE,
)
from apps.integrations.tuya.client import TuyaDeviceConfig, TuyaOfflineError
from apps.jobs.energy_collector import (
    CollectorConfig,
    EnergyCollector,
    configure_energy_collector,
)
from apps.main import app
from apps.models import DeviceCapability
from apps.services.breaker_service import BreakerRegistration, BreakerService
from apps.services.inverter_service import InverterService


class MutableClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 9, 1, 12, 19, 6, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


class FakeBeveClient:
    def __init__(self, *outcomes: Any) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    def fetch_current_telemetry(self) -> dict[str, object]:
        self.calls += 1
        outcome = self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class OverlapDetectingBeveClient:
    def __init__(self) -> None:
        self.active = 0
        self.maximum_active = 0
        self.lock = threading.Lock()

    def fetch_current_telemetry(self) -> dict[str, object]:
        with self.lock:
            self.active += 1
            self.maximum_active = max(self.maximum_active, self.active)
        time.sleep(0.03)
        with self.lock:
            self.active -= 1
        return VERIFIED_BEVE_RESPONSE


class FakeTuyaClient:
    def __init__(self, device_id: str, area: str, *outcomes: Any) -> None:
        self.config = TuyaDeviceConfig(
            device_id=device_id,
            friendly_name=f"{area} breaker",
            area=area,
            local_key="test-only-key",
            ip_address="192.0.2.30",
            protocol_version="3.5",
            enabled=True,
        )
        self.outcomes = list(outcomes)
        self.calls = 0

    def read_status(self) -> dict[str, object]:
        self.calls += 1
        outcome = self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class FakePersistence:
    def __init__(self) -> None:
        self.inverters: list[tuple[str, Any]] = []
        self.breakers: list[tuple[str, Any, datetime]] = []

    def persist_inverter(self, device_reference: str, telemetry) -> None:
        self.inverters.append((device_reference, telemetry))

    def persist_breaker(self, device_reference: str, breaker, collected_at: datetime) -> None:
        self.breakers.append((device_reference, breaker, collected_at))


class FakePublisher:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    async def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        self.events.append((event_type, payload))


def breaker_payload(*, power: float = 0) -> dict[str, object]:
    return {
        "switch": "on",
        "voltage_v": 0,
        "current_ma": 0,
        "power_w": power,
        "energy_total_kwh": 0,
    }


def collector_config(**changes: Any) -> CollectorConfig:
    values = {
        "beve_poll_interval_seconds": 30,
        "tuya_poll_interval_seconds": 10,
        "telemetry_persist_interval_seconds": 60,
        "device_stale_after_seconds": 90,
        "retry_attempts": 1,
        "retry_delay_seconds": 0,
    }
    values.update(changes)
    return CollectorConfig(**values)


def build_collector(
    clock: MutableClock,
    beve: FakeBeveClient,
    breakers: list[FakeTuyaClient],
    *,
    config: CollectorConfig | None = None,
    persistence: FakePersistence | None = None,
    publisher: FakePublisher | None = None,
    sleep=asyncio.sleep,
) -> EnergyCollector:
    capabilities = DeviceCapability(
        switching=True, voltage=True, current=True, instantaneous_power=True, energy_total=True
    )
    breaker_service = BreakerService(
        [BreakerRegistration(client=client, capabilities=capabilities) for client in breakers],
        clock=clock,
    )
    return EnergyCollector(
        InverterService(beve),
        breaker_service,
        inverter_device_reference="inverter-test",
        config=config or collector_config(),
        persistence=persistence,
        publisher=publisher,
        clock=clock,
        sleep=sleep,
    )


@pytest.mark.asyncio
async def test_successful_collection_updates_cache_persistence_and_events() -> None:
    clock = MutableClock()
    persistence = FakePersistence()
    publisher = FakePublisher()
    breaker = FakeTuyaClient("breaker-library", "Library", breaker_payload())
    collector = build_collector(
        clock,
        FakeBeveClient(VERIFIED_BEVE_RESPONSE),
        [breaker],
        persistence=persistence,
        publisher=publisher,
    )

    assert await collector.collect_inverter_once() is True
    assert await collector.collect_breaker_once("breaker-library") is True
    snapshot = await collector.get_snapshot()

    assert snapshot.inverter is not None and snapshot.inverter.grid.voltage == 0
    assert snapshot.breakers["breaker-library"].status.electrical.active_power_watts == 0
    assert snapshot.devices["inverter-test"].online is True
    assert snapshot.devices["breaker-library"].last_seen == clock.now
    assert len(persistence.inverters) == 1
    assert len(persistence.breakers) == 1
    assert {event[0] for event in publisher.events} == {
        "inverter.telemetry", "breaker.telemetry"
    }


@pytest.mark.asyncio
async def test_beve_offline_does_not_stop_breaker_collection() -> None:
    clock = MutableClock()
    breaker = FakeTuyaClient("breaker-library", "Library", breaker_payload())
    collector = build_collector(
        clock, FakeBeveClient(BeveConnectionError("offline")), [breaker]
    )

    inverter_result, breaker_result = await asyncio.gather(
        collector.collect_inverter_once(), collector.collect_breaker_once("breaker-library")
    )
    snapshot = await collector.get_snapshot()

    assert inverter_result is False
    assert breaker_result is True
    assert snapshot.devices["inverter-test"].online is False
    assert snapshot.devices["breaker-library"].online is True


@pytest.mark.asyncio
async def test_one_offline_breaker_does_not_stop_other_breakers_or_beve() -> None:
    clock = MutableClock()
    offline = FakeTuyaClient("breaker-library", "Library", TuyaOfflineError("offline"))
    online = FakeTuyaClient("breaker-admin", "Admin offices", breaker_payload(power=75))
    collector = build_collector(
        clock, FakeBeveClient(VERIFIED_BEVE_RESPONSE), [offline, online]
    )

    results = await asyncio.gather(
        collector.collect_inverter_once(),
        collector.collect_breaker_once("breaker-library"),
        collector.collect_breaker_once("breaker-admin"),
    )
    snapshot = await collector.get_snapshot()

    assert results == [True, False, True]
    assert snapshot.devices["breaker-library"].online is False
    assert snapshot.breakers["breaker-admin"].status.electrical.active_power_watts == 75


@pytest.mark.asyncio
async def test_bounded_retry_and_recovery() -> None:
    clock = MutableClock()
    beve = FakeBeveClient(BeveConnectionError("offline"), VERIFIED_BEVE_RESPONSE)
    collector = build_collector(
        clock, beve, [], config=collector_config(retry_attempts=1)
    )

    assert await collector.collect_inverter_once() is False
    clock.advance(5)
    assert await collector.collect_inverter_once() is True
    snapshot = await collector.get_snapshot()

    assert beve.calls == 2
    assert snapshot.devices["inverter-test"].consecutive_failures == 0
    assert snapshot.devices["inverter-test"].online is True


@pytest.mark.asyncio
async def test_retry_attempts_are_bounded() -> None:
    clock = MutableClock()
    beve = FakeBeveClient(BeveConnectionError("offline"))
    collector = build_collector(
        clock, beve, [], config=collector_config(retry_attempts=3)
    )

    assert await collector.collect_inverter_once() is False
    assert beve.calls == 3


@pytest.mark.asyncio
async def test_timeout_is_tracked_without_stopping_other_sources() -> None:
    clock = MutableClock()
    breaker = FakeTuyaClient("breaker-library", "Library", breaker_payload())
    collector = build_collector(
        clock, FakeBeveClient(BeveTimeoutError("timeout")), [breaker]
    )

    results = await asyncio.gather(
        collector.collect_inverter_once(), collector.collect_breaker_once("breaker-library")
    )

    assert results == [False, True]
    assert (await collector.get_snapshot()).devices["inverter-test"].consecutive_failures == 1


@pytest.mark.asyncio
async def test_stale_detection_uses_last_successful_read() -> None:
    clock = MutableClock()
    collector = build_collector(clock, FakeBeveClient(VERIFIED_BEVE_RESPONSE), [])

    await collector.collect_inverter_once()
    clock.advance(91)
    snapshot = await collector.get_snapshot()

    assert snapshot.devices["inverter-test"].online is True
    assert snapshot.devices["inverter-test"].stale is True


@pytest.mark.asyncio
async def test_persistence_is_throttled_independently_from_live_reads() -> None:
    clock = MutableClock()
    persistence = FakePersistence()
    collector = build_collector(
        clock,
        FakeBeveClient(VERIFIED_BEVE_RESPONSE),
        [],
        config=collector_config(telemetry_persist_interval_seconds=60),
        persistence=persistence,
    )

    await collector.collect_inverter_once()
    clock.advance(10)
    await collector.collect_inverter_once()
    clock.advance(50)
    await collector.collect_inverter_once()

    assert len(persistence.inverters) == 2


@pytest.mark.asyncio
async def test_same_source_poll_cycles_do_not_overlap() -> None:
    clock = MutableClock()
    beve = OverlapDetectingBeveClient()
    collector = build_collector(clock, beve, [])

    results = await asyncio.gather(
        collector.collect_inverter_once(), collector.collect_inverter_once()
    )

    assert results == [True, True]
    assert beve.maximum_active == 1


@pytest.mark.asyncio
async def test_graceful_start_and_cancellation() -> None:
    clock = MutableClock()
    sleep_started = asyncio.Event()
    never_finish = asyncio.Event()

    async def blocking_sleep(seconds: float) -> None:
        sleep_started.set()
        await never_finish.wait()

    collector = build_collector(
        clock,
        FakeBeveClient(VERIFIED_BEVE_RESPONSE),
        [FakeTuyaClient("breaker-library", "Library", breaker_payload())],
        sleep=blocking_sleep,
    )

    await collector.start()
    await asyncio.wait_for(sleep_started.wait(), timeout=2)
    await collector.stop()

    assert collector.running is False
    assert not collector._tasks


def test_application_lifespan_starts_and_stops_configured_collector() -> None:
    class LifecycleCollector:
        started = False
        stopped = False

        async def start(self) -> None:
            self.started = True

        async def stop(self) -> None:
            self.stopped = True

    collector = LifecycleCollector()
    configure_energy_collector(collector)  # type: ignore[arg-type]
    try:
        with TestClient(app) as client:
            assert client.get("/health").status_code == 200
            assert collector.started is True
            assert collector.stopped is False
        assert collector.stopped is True
    finally:
        configure_energy_collector(None)
