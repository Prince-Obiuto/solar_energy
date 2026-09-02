"""Realtime manager, publisher, heartbeat, and WebSocket endpoint tests."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from apps.jobs.energy_collector import configure_energy_collector
from apps.main import app
from apps.core.permissions import get_websocket_user
from apps.realtime.manager import (
    ConnectionManager,
    RealtimeMessage,
    TelemetryEventPublisher,
    connection_manager,
)


class MutableClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 9, 1, 14, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


class FakeWebSocket:
    def __init__(self, *, fail_send: bool = False) -> None:
        self.fail_send = fail_send
        self.accepted = False
        self.closed_with: int | None = None
        self.messages: list[dict[str, Any]] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, payload: dict[str, Any]) -> None:
        if self.fail_send:
            raise RuntimeError("socket failed")
        self.messages.append(payload)

    async def close(self, code: int = 1000) -> None:
        self.closed_with = code


@pytest.mark.asyncio
async def test_multiple_clients_receive_the_same_normalized_event() -> None:
    manager = ConnectionManager(heartbeat_interval_seconds=10, stale_after_seconds=30)
    first = FakeWebSocket()
    second = FakeWebSocket()
    await manager.connect(first)  # type: ignore[arg-type]
    await manager.connect(second)  # type: ignore[arg-type]
    message = RealtimeMessage(
        type="system.status",
        timestamp=datetime.now(UTC),
        data={"status": "ok"},
    )

    await manager.broadcast(message)

    assert first.messages == second.messages
    assert manager.connection_count == 2


@pytest.mark.asyncio
async def test_failed_socket_is_removed_without_affecting_healthy_clients() -> None:
    manager = ConnectionManager(heartbeat_interval_seconds=10, stale_after_seconds=30)
    healthy = FakeWebSocket()
    failed = FakeWebSocket(fail_send=True)
    await manager.connect(healthy)  # type: ignore[arg-type]
    await manager.connect(failed)  # type: ignore[arg-type]

    await manager.broadcast(
        RealtimeMessage(
            type="system.status", timestamp=datetime.now(UTC), data={"status": "ok"}
        )
    )

    assert len(healthy.messages) == 1
    assert manager.connection_count == 1


@pytest.mark.asyncio
async def test_stale_connection_cleanup_closes_inactive_socket() -> None:
    clock = MutableClock()
    manager = ConnectionManager(
        heartbeat_interval_seconds=10,
        stale_after_seconds=30,
        clock=clock,
    )
    socket = FakeWebSocket()
    await manager.connect(socket)  # type: ignore[arg-type]
    clock.now += timedelta(seconds=31)

    await manager.prune_stale()

    assert manager.connection_count == 0
    assert socket.closed_with == 1001


@pytest.mark.asyncio
async def test_manager_sends_periodic_heartbeat_ping() -> None:
    clock = MutableClock()
    first_sleep_complete = False
    block = asyncio.Event()

    async def controlled_sleep(seconds: float) -> None:
        nonlocal first_sleep_complete
        if not first_sleep_complete:
            first_sleep_complete = True
            clock.now += timedelta(seconds=seconds)
            return
        await block.wait()

    manager = ConnectionManager(
        heartbeat_interval_seconds=5,
        stale_after_seconds=30,
        clock=clock,
        sleep=controlled_sleep,
    )
    socket = FakeWebSocket()
    await manager.connect(socket)  # type: ignore[arg-type]

    await manager.start()
    for _ in range(20):
        if socket.messages:
            break
        await asyncio.sleep(0)
    await manager.stop()

    assert socket.messages[0]["type"] == "system.status"
    assert socket.messages[0]["data"]["heartbeat"] == "ping"


@pytest.mark.asyncio
async def test_publisher_emits_documented_inverter_message_types() -> None:
    manager = ConnectionManager(heartbeat_interval_seconds=10, stale_after_seconds=30)
    socket = FakeWebSocket()
    await manager.connect(socket)  # type: ignore[arg-type]
    publisher = TelemetryEventPublisher(manager)
    payload = {
        "timestamp": "2026-09-01T12:19:06Z",
        "device_id": "inverter-test",
        "inverter": {"status": "Battery Mode", "output_power_w": 12},
        "battery": {"soc": 100, "password": "must-not-leak"},
        "solar": {"pv1_power_w": 0},
        "grid": {"power_w": 0, "token": "must-not-leak"},
        "raw_datapoints": {"vendor": "raw"},
    }

    await publisher.publish("inverter.telemetry", payload)

    types = [message["type"] for message in socket.messages]
    serialized = str(socket.messages)
    assert types == [
        "inverter.status", "battery.status", "solar.status", "grid.status",
        "energy.update", "system.status",
    ]
    assert socket.messages[-1]["data"]["data_source"] == "beve_cloud"
    assert "must-not-leak" not in serialized
    assert "raw_datapoints" not in serialized


@pytest.mark.asyncio
async def test_breaker_event_uses_normalized_fields_without_tuya_dps() -> None:
    manager = ConnectionManager(heartbeat_interval_seconds=10, stale_after_seconds=30)
    socket = FakeWebSocket()
    await manager.connect(socket)  # type: ignore[arg-type]
    publisher = TelemetryEventPublisher(manager)
    payload = {
        "id": "breaker-test",
        "online": True,
        "last_seen": "2026-09-01T12:19:06Z",
        "status": {
            "switch_on": True,
            "electrical": {
                "voltage_volts": 195.0,
                "current_amperes": 0.0,
                "active_power_watts": 0.0,
            },
            "energy": {"total_kwh": None},
            "dps": {"1": True},
        },
    }

    await publisher.publish("breaker.telemetry", payload)

    telemetry = socket.messages[0]
    assert telemetry == {
        "type": "breaker.telemetry",
        "device_id": "breaker-test",
        "timestamp": "2026-09-01T12:19:06Z",
        "data": {
            "voltage_v": 195.0,
            "current_a": 0.0,
            "power_w": 0.0,
            "accumulated_energy": None,
        },
    }
    assert "dps" not in str(socket.messages)


def test_websocket_endpoint_heartbeat_and_graceful_disconnect() -> None:
    configure_energy_collector(None)
    app.dependency_overrides[get_websocket_user] = lambda: None
    with TestClient(app) as client:
        with client.websocket_connect("/api/v1/ws/energy") as websocket:
            initial = websocket.receive_json()
            assert initial["type"] == "system.status"
            assert initial["data"]["status"] == "waiting_for_telemetry"
            websocket.send_json({"type": "ping"})
            pong = websocket.receive_json()
            assert pong["type"] == "system.status"
            assert pong["data"]["heartbeat"] == "pong"
        assert connection_manager.connection_count == 0
    app.dependency_overrides.clear()
