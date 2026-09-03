"""Administrator-visible audit and system event routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.core.permissions import require_admin
from apps.db.session import get_db
from apps.models.persistence import AreaRecord, ControlEventRecord, DeviceRecord, SystemEventRecord

router = APIRouter(dependencies=[Depends(require_admin)])

CONTROL_LEVELS = {
    "running": "info", "succeeded": "success", "failed": "error",
    "timed_out": "error", "rejected": "warning",
}
SYSTEM_LEVELS = {
    "debug": "info", "info": "info", "success": "success", "healthy": "success",
    "warning": "warning", "warn": "warning", "error": "error", "critical": "error",
}


def _level(value: str | None, mapping: dict[str, str]) -> str:
    return mapping.get((value or "").lower(), "info")


def _state(value: object) -> str:
    if type(value) is bool:
        return "ON" if value else "OFF"
    return str(value) if value is not None else "unknown"


@router.get("")
async def list_logs(
    limit: int = Query(default=200, ge=1, le=1000),
    session: Session = Depends(get_db),
) -> dict[str, object]:
    """Return bounded persisted events without raw payloads or secrets."""

    system_events = session.scalars(
        select(SystemEventRecord).order_by(SystemEventRecord.timestamp.desc()).limit(limit)
    ).all()
    control_events = session.scalars(
        select(ControlEventRecord).order_by(ControlEventRecord.timestamp.desc()).limit(limit)
    ).all()
    devices = {
        item.id: item for item in session.scalars(select(DeviceRecord)).all()
    }
    areas = {item.id: item for item in session.scalars(select(AreaRecord)).all()}
    items = [
        {
            "id": str(event.id), "category": event.category,
            "level": _level(event.severity, SYSTEM_LEVELS), "raw_status": event.severity,
            "title": event.category.replace(".", " ").title(), "message": event.message,
            "timestamp": event.timestamp, "actor": "System", "source": "backend",
        }
        for event in system_events
    ] + [
        _control_log(event, devices.get(event.device_id), areas.get(event.area_id))
        for event in control_events
    ]
    items.sort(key=lambda item: item["timestamp"], reverse=True)
    bounded = items[:limit]
    return {"items": bounded, "total": len(bounded)}


def _control_log(event, device, area) -> dict[str, object]:
    name = device.friendly_name if device else "Breaker"
    action = (event.action or event.command).replace("_", " ").title()
    successful_switch = event.status == "succeeded" and (event.action or event.command) == "switch"
    title = (
        f"{name} — Turned {_state(event.verified_value)}" if successful_switch
        else f"{name} — {action} command failed" if event.status in {"failed", "timed_out", "rejected"}
        else f"{name} — {action}"
    )
    return {
        "id": str(event.id), "category": "Controls",
        "level": _level(event.status, CONTROL_LEVELS), "raw_status": event.status,
        "title": title,
        "message": event.error_information or "Breaker control request completed",
        "timestamp": event.timestamp, "requested_at": event.requested_at,
        "completed_at": event.completed_at,
        "actor": event.requested_by or "Unknown user", "requested_by": event.requested_by,
        "role": event.role, "source": "breaker control", "device": name,
        "area": area.name if area else None, "action": event.action or event.command,
        "previous_value": event.previous_value, "requested_value": event.requested_value,
        "verified_value": event.verified_value, "status": event.status,
        "reason": event.reason, "error_information": event.error_information,
    }
