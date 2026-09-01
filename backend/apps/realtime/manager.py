"""WebSocket connection management and normalized collector event publication."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastapi import WebSocket
from pydantic import Field, field_validator

from apps.core.config import settings
from apps.models import DomainModel

if TYPE_CHECKING:
    from apps.jobs.energy_collector import CollectorSnapshot


MESSAGE_TYPES = frozenset(
    {
        "inverter.status",
        "battery.status",
        "solar.status",
        "grid.status",
        "breaker.telemetry",
        "breaker.status",
        "device.online",
        "device.offline",
        "energy.update",
        "alert.created",
        "system.status",
    }
)
SENSITIVE_KEYS = frozenset(
    {"password", "token", "secret", "local_key", "ip_address", "dps", "raw_datapoints"}
)


class RealtimeMessage(DomainModel):
    """Normalized envelope sent to every realtime consumer."""

    type: str
    device_id: str | None = None
    timestamp: datetime
    data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("type")
    @classmethod
    def supported_type(cls, value: str) -> str:
        if value not in MESSAGE_TYPES:
            raise ValueError("Unsupported realtime message type")
        return value


class ManagedConnection:
    def __init__(self, websocket: WebSocket, connected_at: datetime) -> None:
        self.websocket = websocket
        self.last_activity = connected_at
        self.send_lock = asyncio.Lock()


class ConnectionManager:
    """Manage multiple sockets without allowing one failure to affect others."""

    def __init__(
        self,
        *,
        heartbeat_interval_seconds: float | None = None,
        stale_after_seconds: float | None = None,
        clock=None,
        sleep=asyncio.sleep,
    ) -> None:
        self.heartbeat_interval_seconds = (
            heartbeat_interval_seconds or settings.websocket_heartbeat_interval_seconds
        )
        self.stale_after_seconds = stale_after_seconds or settings.websocket_stale_after_seconds
        self._clock = clock or (lambda: datetime.now(UTC))
        self._sleep = sleep
        self._connections: dict[int, ManagedConnection] = {}
        self._lock = asyncio.Lock()
        self._heartbeat_task: asyncio.Task[None] | None = None

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    async def start(self) -> None:
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(
                self._heartbeat_loop(), name="websocket-heartbeat"
            )

    async def stop(self) -> None:
        task = self._heartbeat_task
        self._heartbeat_task = None
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        async with self._lock:
            connections = tuple(self._connections.values())
            self._connections.clear()
        await asyncio.gather(
            *(self._safe_close(connection.websocket, 1001) for connection in connections),
            return_exceptions=True,
        )

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[id(websocket)] = ManagedConnection(websocket, self._clock())

    async def disconnect(self, websocket: WebSocket, *, close_code: int | None = None) -> None:
        async with self._lock:
            connection = self._connections.pop(id(websocket), None)
        if connection is not None and close_code is not None:
            await self._safe_close(websocket, close_code)

    async def touch(self, websocket: WebSocket) -> None:
        async with self._lock:
            connection = self._connections.get(id(websocket))
            if connection is not None:
                connection.last_activity = self._clock()

    async def send(self, websocket: WebSocket, message: RealtimeMessage) -> bool:
        async with self._lock:
            connection = self._connections.get(id(websocket))
        if connection is None:
            return False
        try:
            async with connection.send_lock:
                await websocket.send_json(message.model_dump(mode="json"))
            return True
        except Exception:
            await self.disconnect(websocket)
            return False

    async def broadcast(self, message: RealtimeMessage) -> None:
        async with self._lock:
            sockets = [connection.websocket for connection in self._connections.values()]
        if sockets:
            await asyncio.gather(*(self.send(socket, message) for socket in sockets))

    async def prune_stale(self) -> None:
        now = self._clock()
        async with self._lock:
            stale = [
                connection.websocket
                for connection in self._connections.values()
                if (now - connection.last_activity).total_seconds() >= self.stale_after_seconds
            ]
        await asyncio.gather(
            *(self.disconnect(websocket, close_code=1001) for websocket in stale),
            return_exceptions=True,
        )

    async def _heartbeat_loop(self) -> None:
        try:
            while True:
                await self._sleep(self.heartbeat_interval_seconds)
                await self.prune_stale()
                await self.broadcast(
                    RealtimeMessage(
                        type="system.status",
                        timestamp=self._clock(),
                        data={"status": "ok", "heartbeat": "ping"},
                    )
                )
        except asyncio.CancelledError:
            raise

    @staticmethod
    async def _safe_close(websocket: WebSocket, code: int) -> None:
        try:
            await websocket.close(code=code)
        except Exception:
            return


def sanitize_payload(value: Any) -> Any:
    """Recursively remove connection details and vendor/raw data from events."""

    if isinstance(value, dict):
        return {
            key: sanitize_payload(item)
            for key, item in value.items()
            if key.lower() not in SENSITIVE_KEYS
            and not any(fragment in key.lower() for fragment in ("password", "token", "secret"))
        }
    if isinstance(value, list):
        return [sanitize_payload(item) for item in value]
    return value


class TelemetryEventPublisher:
    """Translate collector events into the documented realtime message contract."""

    def __init__(self, manager: ConnectionManager, *, clock=None) -> None:
        self.manager = manager
        self._clock = clock or (lambda: datetime.now(UTC))

    async def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        for message in self.messages_for_event(event_type, sanitize_payload(payload)):
            await self.manager.broadcast(message)

    async def send_snapshot(self, websocket: WebSocket, snapshot: CollectorSnapshot) -> None:
        for message in self.messages_for_snapshot(snapshot):
            await self.manager.send(websocket, message)

    def messages_for_event(
        self, event_type: str, payload: dict[str, Any]
    ) -> list[RealtimeMessage]:
        timestamp = self._timestamp(payload.get("timestamp") or payload.get("last_seen"))
        if event_type == "inverter.telemetry":
            categories = ("inverter", "battery", "solar", "grid")
            messages = [
                RealtimeMessage(
                    type=f"{category}.status",
                    timestamp=timestamp,
                    data=sanitize_payload(payload.get(category) or {}),
                )
                for category in categories
            ]
            messages.extend(
                [
                    RealtimeMessage(
                        type="energy.update",
                        timestamp=timestamp,
                        data={category: sanitize_payload(payload.get(category) or {}) for category in categories},
                    ),
                    RealtimeMessage(
                        type="device.online",
                        device_id=payload.get("device_id"),
                        timestamp=timestamp,
                        data={"online": True},
                    ),
                ]
            )
            return messages
        if event_type == "breaker.telemetry":
            return self._breaker_messages(payload, timestamp)
        if event_type == "breaker.offline":
            device_id = payload.get("device_id")
            return [
                RealtimeMessage(
                    type="breaker.status", device_id=device_id, timestamp=timestamp,
                    data={"online": False, "switch_state": None},
                ),
                RealtimeMessage(
                    type="device.offline", device_id=device_id, timestamp=timestamp,
                    data={"online": False},
                ),
            ]
        if event_type in MESSAGE_TYPES:
            return [
                RealtimeMessage(
                    type=event_type,
                    device_id=payload.get("device_id"),
                    timestamp=timestamp,
                    data=sanitize_payload(payload.get("data", payload)),
                )
            ]
        return []

    def messages_for_snapshot(self, snapshot: CollectorSnapshot) -> list[RealtimeMessage]:
        messages: list[RealtimeMessage] = []
        if snapshot.inverter is not None:
            messages.extend(
                self.messages_for_event(
                    "inverter.telemetry", snapshot.inverter.model_dump(mode="json")
                )
            )
        for breaker in snapshot.breakers.values():
            messages.extend(
                self.messages_for_event("breaker.telemetry", breaker.model_dump(mode="json"))
            )
        return messages

    def _breaker_messages(
        self, payload: dict[str, Any], timestamp: datetime
    ) -> list[RealtimeMessage]:
        device_id = payload.get("id") or payload.get("device_id")
        status = payload.get("status") if isinstance(payload.get("status"), dict) else {}
        electrical = status.get("electrical") if isinstance(status.get("electrical"), dict) else {}
        energy = status.get("energy") if isinstance(status.get("energy"), dict) else {}
        online = bool(payload.get("online"))
        return [
            RealtimeMessage(
                type="breaker.telemetry",
                device_id=device_id,
                timestamp=timestamp,
                data={
                    "voltage_v": electrical.get("voltage_volts"),
                    "current_a": electrical.get("current_amperes"),
                    "power_w": electrical.get("active_power_watts"),
                    "accumulated_energy": energy.get("total_kwh"),
                },
            ),
            RealtimeMessage(
                type="breaker.status",
                device_id=device_id,
                timestamp=timestamp,
                data={"online": online, "switch_state": status.get("switch_on")},
            ),
            RealtimeMessage(
                type="device.online" if online else "device.offline",
                device_id=device_id,
                timestamp=timestamp,
                data={"online": online},
            ),
        ]

    def _timestamp(self, value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                pass
        return self._clock()


connection_manager = ConnectionManager()
telemetry_event_publisher = TelemetryEventPublisher(connection_manager)
