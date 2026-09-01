"""Normalized dashboard aggregation response schemas."""

from datetime import datetime
from enum import Enum

from pydantic import Field

from apps.models import (
    BatteryTelemetryStatus, DomainModel, GridTelemetryStatus,
    InverterTelemetryStatus, SolarTelemetryStatus,
)


class OverallHealth(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class DashboardSystem(DomainModel):
    overall_health: OverallHealth
    last_update: datetime | None = None
    online_devices: int = Field(ge=0)
    offline_devices: int = Field(ge=0)
    stale_devices: int = Field(ge=0)
    active_alerts: int = Field(ge=0)


class DashboardArea(DomainModel):
    device_id: str
    area: str
    online: bool
    is_on: bool | None = None
    voltage_v: float | None = None
    current_a: float | None = None
    power_w: float | None = None
    accumulated_energy: float | None = None
    last_seen: datetime | None = None


class DashboardSnapshot(DomainModel):
    system: DashboardSystem
    inverter: InverterTelemetryStatus = Field(default_factory=InverterTelemetryStatus)
    battery: BatteryTelemetryStatus = Field(default_factory=BatteryTelemetryStatus)
    solar: SolarTelemetryStatus = Field(default_factory=SolarTelemetryStatus)
    grid: GridTelemetryStatus = Field(default_factory=GridTelemetryStatus)
    areas: list[DashboardArea] = Field(default_factory=list)


class DashboardAreas(DomainModel):
    last_update: datetime | None = None
    items: list[DashboardArea] = Field(default_factory=list)
    total: int = Field(ge=0)
