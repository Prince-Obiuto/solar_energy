"""Read-only unified device API routes."""

from fastapi import APIRouter, Depends, HTTPException, status

from apps.models import RegisteredDevice
from apps.services.device_service import DeviceNotFoundError, DeviceService, get_device_service

router = APIRouter()


@router.get("")
async def list_devices(
    service: DeviceService = Depends(get_device_service),
) -> dict[str, object]:
    devices = service.get_devices()
    return {"items": devices, "total": len(devices)}


@router.get("/{device_id}", response_model=RegisteredDevice)
async def retrieve_device(
    device_id: str,
    service: DeviceService = Depends(get_device_service),
) -> RegisteredDevice:
    try:
        return service.get_device(device_id)
    except DeviceNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found") from None
