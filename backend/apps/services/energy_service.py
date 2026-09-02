"""Unified current energy snapshot application service."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import Field

from apps.models import (
    BatteryTelemetryStatus,
    BreakerDevice,
    DomainModel,
    GridTelemetryStatus,
    InverterTelemetryStatus,
    SolarTelemetryStatus,
)

from .breaker_service import BreakerService, get_breaker_service
from .inverter_service import InverterService, get_inverter_service


class CurrentEnergySnapshot(DomainModel):
    """Current normalized BEVE and area-breaker telemetry."""

    captured_at: datetime
    inverter: InverterTelemetryStatus
    battery: BatteryTelemetryStatus
    solar: SolarTelemetryStatus
    grid: GridTelemetryStatus
    breakers: list[BreakerDevice] = Field(default_factory=list)


class EnergyService:
    def __init__(self, inverter_service: InverterService, breaker_service: BreakerService) -> None:
        self._inverter = inverter_service
        self._breakers = breaker_service

    def get_latest_snapshot(self) -> CurrentEnergySnapshot:
        inverter = self._inverter.get_current_state()
        return CurrentEnergySnapshot(
            captured_at=datetime.now(UTC),
            inverter=inverter.inverter,
            battery=inverter.battery,
            solar=inverter.solar,
            grid=inverter.grid,
            breakers=self._breakers.list_breakers(),
        )


_default_energy_service = EnergyService(get_inverter_service(), get_breaker_service())


def get_energy_service() -> EnergyService:
    """FastAPI dependency for unified current energy telemetry."""

    from apps.core.runtime import get_application_runtime
    runtime = get_application_runtime()
    if runtime is not None:
        return runtime.energy_service
    return _default_energy_service


def get_energy_summary() -> dict[str, object]:
    """Compatibility summary derived from the current normalized snapshot."""

    snapshot = get_energy_service().get_latest_snapshot()
    return snapshot.model_dump(mode="json")


def list_energy_points() -> list[dict[str, object]]:
    """Historical points remain unavailable until a persistence phase."""

    return []
