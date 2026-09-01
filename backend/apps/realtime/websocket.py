"""Realtime energy WebSocket endpoint backed only by collector state/events."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from apps.jobs.energy_collector import get_energy_collector
from apps.core.permissions import get_websocket_user
from apps.models.persistence import UserRecord

from .manager import RealtimeMessage, connection_manager, telemetry_event_publisher


router = APIRouter()


@router.websocket("/energy")
async def energy_websocket(
    websocket: WebSocket,
    user: UserRecord = Depends(get_websocket_user),
) -> None:
    await connection_manager.connect(websocket)
    collector = get_energy_collector()
    if collector is not None:
        await telemetry_event_publisher.send_snapshot(websocket, await collector.get_snapshot())
    else:
        await connection_manager.send(
            websocket,
            RealtimeMessage(
                type="system.status",
                timestamp=datetime.now(UTC),
                data={"status": "waiting_for_telemetry"},
            ),
        )
    try:
        while True:
            message = await websocket.receive_json()
            await connection_manager.touch(websocket)
            if isinstance(message, dict) and message.get("type") == "ping":
                await connection_manager.send(
                    websocket,
                    RealtimeMessage(
                        type="system.status",
                        timestamp=datetime.now(UTC),
                        data={"status": "ok", "heartbeat": "pong"},
                    ),
                )
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        await connection_manager.disconnect(websocket)
