"""Read-only unified device API routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apps.db.session import get_db
from apps.jobs.energy_collector import CollectorSnapshot, get_energy_collector
from apps.models import RegisteredDevice
from apps.services.breaker_monitoring_service import BreakerMonitoringService
from apps.services.device_service import DeviceService, get_device_service

router = APIRouter()


@router.get("")
async def list_devices(
    session: Session = Depends(get_db),
    service: DeviceService = Depends(get_device_service),
) -> dict[str, object]:
    collector = get_energy_collector()
    snapshot = await collector.get_snapshot() if collector else CollectorSnapshot()
    breakers = await BreakerMonitoringService(
        session, service.breaker_service, collector
    ).list_breakers()
    devices = service.get_cached_devices(snapshot, breakers)
    return {"items": devices, "total": len(devices)}


@router.get("/{device_id}", response_model=RegisteredDevice)
async def retrieve_device(
    device_id: str,
    session: Session = Depends(get_db),
    service: DeviceService = Depends(get_device_service),
) -> RegisteredDevice:
    response = await list_devices(session=session, service=service)
    for device in response["items"]:
        if device.id == device_id:
            return device
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
