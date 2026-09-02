"""Normalized smart-breaker domain model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from .device import (
    ConnectivityType, DataFreshness, DataSource, DataStatus, DeviceCapability,
    DeviceFault, DeviceStatus, DeviceType, DomainModel, SourceStatus,
)
from .energy_reading import ElectricalMeasurement, EnergyMeasurement


class BreakerStatus(DomainModel):
    """Current normalized state of a breaker or protection device."""

    device_id: str | None = None
    name: str = "breaker"
    device_type: DeviceType = DeviceType.BREAKER
    status: DeviceStatus = DeviceStatus.UNKNOWN
    switch_on: bool | None = None
    electrical: ElectricalMeasurement = Field(default_factory=ElectricalMeasurement)
    energy: EnergyMeasurement = Field(default_factory=EnergyMeasurement)
    countdown_seconds: int | None = Field(default=None, ge=0)
    faults: list[DeviceFault] = Field(default_factory=list)
    configuration: dict[str, Any] | None = None


BreakerState = BreakerStatus


class BreakerDevice(DomainModel):
    """Secret-free breaker registry and latest telemetry view."""

    id: str = Field(min_length=1)
    friendly_name: str = Field(min_length=1)
    area: str = Field(min_length=1)
    online: bool
    connectivity_type: ConnectivityType = ConnectivityType.LOCAL
    data_source: DataSource = DataSource.TINYTUYA
    data_status: DataStatus | None = None
    last_seen: datetime | None = None
    capabilities: DeviceCapability = Field(default_factory=DeviceCapability)
    status: BreakerStatus

    def model_post_init(self, __context) -> None:
        if self.data_status is None:
            self.data_status = DataStatus(
                connectivity_type=ConnectivityType.LOCAL,
                data_source=DataSource.TINYTUYA,
                available=self.online,
                stale=not self.online,
                source_status=SourceStatus.CONNECTED if self.online else SourceStatus.UNREACHABLE,
                data_freshness=DataFreshness.LIVE if self.online else DataFreshness.UNAVAILABLE,
                last_successful_update=self.last_seen,
            )
