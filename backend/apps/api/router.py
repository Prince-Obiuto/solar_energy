"""Root router for versioned API endpoints."""

from fastapi import APIRouter, Depends

from apps.api import auth, breakers, controls, dashboard, devices, energy, inverter, logs, reports, users
from apps.core.config import settings
from apps.core.permissions import require_admin, require_staff, require_student
from apps.realtime.websocket import router as websocket_router


api_router = APIRouter()


@api_router.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Return the versioned API health status."""

    return {
        "status": "ok",
        "service": "solar-energy-backend",
        "version": settings.app_version,
    }


api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(breakers.router, prefix="/breakers", tags=["breakers"], dependencies=[Depends(require_staff)])
api_router.include_router(controls.router, prefix="/controls", tags=["controls"], dependencies=[Depends(require_admin)])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(require_student)])
api_router.include_router(devices.router, prefix="/devices", tags=["devices"], dependencies=[Depends(require_staff)])
api_router.include_router(energy.router, prefix="/energy", tags=["energy"], dependencies=[Depends(require_student)])
api_router.include_router(inverter.router, prefix="/inverter", tags=["inverter"], dependencies=[Depends(require_staff)])
api_router.include_router(logs.router, prefix="/logs", tags=["logs"], dependencies=[Depends(require_admin)])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"], dependencies=[Depends(require_student)])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(websocket_router, prefix="/ws", tags=["realtime"])
