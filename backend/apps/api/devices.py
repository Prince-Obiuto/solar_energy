"""Device API routes."""

from fastapi import APIRouter

from apps.services.device_service import get_devices

router = APIRouter()


@router.get("")
async def list_devices() -> dict[str, object]:
    """Return the current device list in normalized domain format."""

    devices = get_devices()
    return {"items": [device.__dict__ for device in devices], "total": len(devices)}

