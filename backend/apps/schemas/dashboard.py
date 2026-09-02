"""Normalized dashboard aggregation response schemas."""

from datetime import datetime
from enum import Enum

from pydantic import Field

from apps.models import (
    BatteryTelemetryStatus, ConnectivityType, DataFreshness, DataSource, DataStatus, DomainModel, GridTelemetryStatus,
    InverterTelemetryStatus, SolarTelemetryStatus,
    SourceStatus,
)


class OverallHealth(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class ComponentHealth(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class DashboardSystem(DomainModel):
    overall_health: OverallHealth
    system_status: OverallHealth = OverallHealth.UNKNOWN
    components: dict[str, ComponentHealth] = Field(default_factory=dict)
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
    data_status: DataStatus = Field(default_factory=lambda: DataStatus(
        connectivity_type=ConnectivityType.CLOUD,
        data_source=DataSource.BEVE_CLOUD,
        source_status=SourceStatus.UNKNOWN,
        data_freshness=DataFreshness.UNAVAILABLE,
    ))
    areas: list[DashboardArea] = Field(default_factory=list)


class DashboardAreas(DomainModel):
    last_update: datetime | None = None
    items: list[DashboardArea] = Field(default_factory=list)
    total: int = Field(ge=0)
