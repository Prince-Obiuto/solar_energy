"""Dashboard API routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.db.session import get_db
from apps.jobs.energy_collector import get_energy_collector
from apps.schemas.dashboard import DashboardAreas, DashboardSnapshot, DashboardSystem
from apps.services.dashboard_service import DashboardService

router = APIRouter()


def get_dashboard_service(session: Session = Depends(get_db)) -> DashboardService:
    return DashboardService(session, get_energy_collector())


@router.get("", response_model=DashboardSnapshot)
async def get_dashboard(
    service: DashboardService = Depends(get_dashboard_service),
) -> DashboardSnapshot:
    """Return one cache-first snapshot for all dashboard widgets."""

    return await service.get_dashboard()


@router.get("/summary", response_model=DashboardSystem)
async def get_dashboard_summary(
    service: DashboardService = Depends(get_dashboard_service),
) -> DashboardSystem:
    return await service.get_summary()


@router.get("/areas", response_model=DashboardAreas)
async def get_dashboard_areas(
    service: DashboardService = Depends(get_dashboard_service),
) -> DashboardAreas:
    return await service.get_areas()
