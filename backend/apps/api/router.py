"""Root router for versioned API endpoints."""

from fastapi import APIRouter

from apps.api import auth, breakers, controls, dashboard, devices, energy, logs, reports
from apps.core.config import settings


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
api_router.include_router(breakers.router, prefix="/breakers", tags=["breakers"])
api_router.include_router(controls.router, prefix="/controls", tags=["controls"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(devices.router, prefix="/devices", tags=["devices"])
api_router.include_router(energy.router, prefix="/energy", tags=["energy"])
api_router.include_router(logs.router, prefix="/logs", tags=["logs"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
