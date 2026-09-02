"""Administrator-visible audit and system event routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.core.permissions import require_admin
from apps.db.session import get_db
from apps.models.persistence import ControlEventRecord, SystemEventRecord

router = APIRouter(dependencies=[Depends(require_admin)])


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
    items = [
        {
            "id": str(event.id), "category": event.category, "level": event.severity,
            "title": event.category.replace(".", " ").title(), "message": event.message,
            "timestamp": event.timestamp, "actor": "System", "source": "backend",
        }
        for event in system_events
    ] + [
        {
            "id": str(event.id), "category": "Controls", "level": event.status,
            "title": (event.action or event.command).replace("_", " ").title(),
            "message": event.error_information or "Breaker control request completed",
            "timestamp": event.timestamp, "actor": event.requested_by or "Unknown user",
            "source": "breaker control",
        }
        for event in control_events
    ]
    items.sort(key=lambda item: item["timestamp"], reverse=True)
    bounded = items[:limit]
    return {"items": bounded, "total": len(bounded)}
