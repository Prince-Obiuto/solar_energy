"""Energy API routes."""

from fastapi import APIRouter

from apps.services.energy_service import list_energy_points

router = APIRouter()


@router.get("")
async def list_energy() -> dict[str, object]:
    """Return normalized energy telemetry points for the frontend dashboard."""

    return {"items": list_energy_points(), "total": len(list_energy_points())}

