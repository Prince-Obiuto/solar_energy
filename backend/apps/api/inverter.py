"""Strictly read-only normalized inverter API routes."""

from fastapi import APIRouter, Depends, HTTPException, status

from apps.models import (
    BatteryTelemetryStatus,
    GridTelemetryStatus,
    InverterTelemetry,
    SolarTelemetryStatus,
)
from apps.services.inverter_service import (
    InverterService,
    ServiceUnavailableError,
    get_inverter_service,
)

router = APIRouter()


def unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Inverter telemetry is unavailable",
    )


@router.get("", response_model=InverterTelemetry)
async def current_inverter(
    service: InverterService = Depends(get_inverter_service),
) -> InverterTelemetry:
    try:
        return service.get_current_state()
    except ServiceUnavailableError:
        raise unavailable() from None


@router.get("/battery", response_model=BatteryTelemetryStatus)
async def current_battery(
    service: InverterService = Depends(get_inverter_service),
) -> BatteryTelemetryStatus:
    try:
        return service.get_battery_state()
    except ServiceUnavailableError:
        raise unavailable() from None


@router.get("/solar", response_model=SolarTelemetryStatus)
async def current_solar(
    service: InverterService = Depends(get_inverter_service),
) -> SolarTelemetryStatus:
    try:
        return service.get_solar_state()
    except ServiceUnavailableError:
        raise unavailable() from None


@router.get("/grid", response_model=GridTelemetryStatus)
async def current_grid(
    service: InverterService = Depends(get_inverter_service),
) -> GridTelemetryStatus:
    try:
        return service.get_grid_state()
    except ServiceUnavailableError:
        raise unavailable() from None
