"""Strictly read-only normalized inverter API routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from apps.db.session import get_db
from apps.jobs.energy_collector import get_energy_collector
from apps.models import (
    BatteryTelemetryStatus,
    GridTelemetryStatus,
    InverterTelemetry,
    SolarTelemetryStatus,
)
from apps.services.dashboard_service import DashboardService

router = APIRouter()


def unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Inverter telemetry is unavailable",
    )


@router.get("", response_model=InverterTelemetry)
async def current_inverter(
    session: Session = Depends(get_db),
) -> InverterTelemetry:
    snapshot = await DashboardService(session, get_energy_collector()).get_dashboard()
    timestamp = snapshot.data_status.source_timestamp
    if timestamp is None:
        raise unavailable()
    return InverterTelemetry(
        timestamp=timestamp, inverter=snapshot.inverter, battery=snapshot.battery,
        solar=snapshot.solar, grid=snapshot.grid,
    )


@router.get("/battery", response_model=BatteryTelemetryStatus)
async def current_battery(
    session: Session = Depends(get_db),
) -> BatteryTelemetryStatus:
    return (await current_inverter(session)).battery


@router.get("/solar", response_model=SolarTelemetryStatus)
async def current_solar(
    session: Session = Depends(get_db),
) -> SolarTelemetryStatus:
    return (await current_inverter(session)).solar


@router.get("/grid", response_model=GridTelemetryStatus)
async def current_grid(
    session: Session = Depends(get_db),
) -> GridTelemetryStatus:
    return (await current_inverter(session)).grid
