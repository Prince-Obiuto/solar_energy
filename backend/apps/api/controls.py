"""Secret-free inventory of ADMIN-eligible breaker controls."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.db.session import get_db
from apps.jobs.energy_collector import get_energy_collector
from apps.services.breaker_monitoring_service import BreakerMonitoringService
from apps.services.breaker_service import BreakerService, get_breaker_service

router = APIRouter()


@router.get("")
async def list_controls(
    session: Session = Depends(get_db),
    service: BreakerService = Depends(get_breaker_service),
) -> dict[str, object]:
    """Return normalized breaker controls; inverter control does not exist."""

    items = []
    monitoring = BreakerMonitoringService(session, service, get_energy_collector())
    for breaker in await monitoring.list_breakers():
        capabilities = breaker.capabilities
        actions = []
        if capabilities.switching:
            actions.append("switch")
        if capabilities.countdown:
            actions.append("countdown")
        if capabilities.remote_configuration:
            actions.extend(("relay_restore_mode", "indicator_mode", "child_lock"))
        items.append({
            "device_id": breaker.id,
            "friendly_name": breaker.friendly_name,
            "area": breaker.area,
            "online": breaker.online,
            "switch_on": breaker.status.switch_on,
            "actions": actions,
        })
    return {"items": items, "total": len(items)}
