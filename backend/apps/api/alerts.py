"""Staff-visible alert lifecycle routes."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from apps.core.permissions import require_staff
from apps.db.session import get_db
from apps.models.persistence import UserRecord
from apps.realtime.manager import telemetry_event_publisher
from apps.schemas.alert import AlertList, AlertSeverity, AlertView
from apps.services.alert_service import AlertNotFoundError, AlertService


router = APIRouter(dependencies=[Depends(require_staff)])


@router.get("", response_model=AlertList)
async def list_alerts(
    active: bool | None = True,
    severity: AlertSeverity | None = None,
    category: str | None = None,
    device_id: str | None = None,
    area_id: UUID | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    session: Session = Depends(get_db),
) -> AlertList:
    return AlertService(session).list_alerts(
        active=active, severity=severity, category=category,
        device_id=device_id, area_id=area_id, limit=limit,
    )


@router.get("/{alert_id}", response_model=AlertView)
async def get_alert(alert_id: UUID, session: Session = Depends(get_db)) -> AlertView:
    try:
        return AlertService(session).get_alert(alert_id)
    except AlertNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found") from None


@router.post("/{alert_id}/acknowledge", response_model=AlertView)
async def acknowledge_alert(
    alert_id: UUID,
    user: UserRecord = Depends(require_staff),
    session: Session = Depends(get_db),
) -> AlertView:
    service = AlertService(session)
    try:
        alert = service.acknowledge(alert_id, user)
    except AlertNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found") from None
    view = service.view(alert)
    await telemetry_event_publisher.publish(
        "alert.acknowledged",
        {"device_id": view.device, "timestamp": view.acknowledged_at, "data": view.model_dump(mode="json")},
    )
    return view
