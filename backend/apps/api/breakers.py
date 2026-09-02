"""Read-only normalized breaker API routes."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from apps.models import BreakerDevice, CommandResult
from apps.core.permissions import require_admin
from apps.db.session import get_db
from apps.models.persistence import UserRecord
from apps.schemas.control import (
    ChildLockRequest, CountdownRequest, IndicatorModeRequest,
    RelayRestoreModeRequest, SwitchRequest,
)
from apps.services.control_service import BreakerControlService
from apps.realtime.manager import telemetry_event_publisher
from apps.services.breaker_service import (
    BreakerNotFoundError,
    BreakerService,
    get_breaker_service,
)

router = APIRouter()


@router.get("")
async def list_breakers(
    service: BreakerService = Depends(get_breaker_service),
) -> dict[str, object]:
    breakers = service.list_breakers()
    return {"items": breakers, "total": len(breakers)}


@router.get("/{breaker_id}", response_model=BreakerDevice)
async def retrieve_breaker(
    breaker_id: str,
    service: BreakerService = Depends(get_breaker_service),
) -> BreakerDevice:
    try:
        return service.get_breaker(breaker_id)
    except BreakerNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Breaker not found") from None


async def execute_control(
    *,
    breaker_id: str,
    action: str,
    value,
    request_id,
    reason: str | None,
    request: Request,
    user: UserRecord,
    session: Session,
    breakers: BreakerService,
) -> CommandResult:
    try:
        service = BreakerControlService(session, breakers)
        result = service.execute(
            request_id=str(request_id), breaker_id=breaker_id, action=action,
            requested_value=value, user=user, reason=reason,
            client_ip=request.client.host if request.client else None,
        )
        for event_type, alert in service.alert_changes:
            await telemetry_event_publisher.publish(
                event_type,
                {"device_id": alert.device, "timestamp": alert.last_seen, "data": alert.model_dump(mode="json")},
            )
        return result
    except BreakerNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Breaker not found") from None


@router.post("/{breaker_id}/switch", response_model=CommandResult)
async def switch_breaker(
    breaker_id: str, payload: SwitchRequest, request: Request,
    user: UserRecord = Depends(require_admin), session: Session = Depends(get_db),
    breakers: BreakerService = Depends(get_breaker_service),
) -> CommandResult:
    return await execute_control(breaker_id=breaker_id, action="switch", value=payload.state, request_id=payload.request_id, reason=payload.reason, request=request, user=user, session=session, breakers=breakers)


@router.put("/{breaker_id}/countdown", response_model=CommandResult)
async def set_countdown(
    breaker_id: str, payload: CountdownRequest, request: Request,
    user: UserRecord = Depends(require_admin), session: Session = Depends(get_db),
    breakers: BreakerService = Depends(get_breaker_service),
) -> CommandResult:
    return await execute_control(breaker_id=breaker_id, action="countdown", value=payload.seconds, request_id=payload.request_id, reason=payload.reason, request=request, user=user, session=session, breakers=breakers)


@router.put("/{breaker_id}/relay-restore-mode", response_model=CommandResult)
async def set_relay_restore_mode(
    breaker_id: str, payload: RelayRestoreModeRequest, request: Request,
    user: UserRecord = Depends(require_admin), session: Session = Depends(get_db),
    breakers: BreakerService = Depends(get_breaker_service),
) -> CommandResult:
    return await execute_control(breaker_id=breaker_id, action="relay_restore_mode", value=payload.mode.value, request_id=payload.request_id, reason=payload.reason, request=request, user=user, session=session, breakers=breakers)


@router.put("/{breaker_id}/indicator-mode", response_model=CommandResult)
async def set_indicator_mode(
    breaker_id: str, payload: IndicatorModeRequest, request: Request,
    user: UserRecord = Depends(require_admin), session: Session = Depends(get_db),
    breakers: BreakerService = Depends(get_breaker_service),
) -> CommandResult:
    return await execute_control(breaker_id=breaker_id, action="indicator_mode", value=payload.mode.value, request_id=payload.request_id, reason=payload.reason, request=request, user=user, session=session, breakers=breakers)


@router.put("/{breaker_id}/child-lock", response_model=CommandResult)
async def set_child_lock(
    breaker_id: str, payload: ChildLockRequest, request: Request,
    user: UserRecord = Depends(require_admin), session: Session = Depends(get_db),
    breakers: BreakerService = Depends(get_breaker_service),
) -> CommandResult:
    return await execute_control(breaker_id=breaker_id, action="child_lock", value=payload.enabled, request_id=payload.request_id, reason=payload.reason, request=request, user=user, session=session, breakers=breakers)
