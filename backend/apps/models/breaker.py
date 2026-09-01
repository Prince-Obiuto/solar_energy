"""Normalized smart-breaker domain model."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from .device import DeviceCapability, DeviceFault, DeviceStatus, DeviceType, DomainModel
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
    last_seen: datetime | None = None
    capabilities: DeviceCapability = Field(default_factory=DeviceCapability)
    status: BreakerStatus
