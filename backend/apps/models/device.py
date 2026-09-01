"""Vendor-neutral device domain models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DomainModel(BaseModel):
    """Base configuration shared by normalized domain models."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, validate_assignment=True)


class DeviceType(str, Enum):
    """Device categories understood by the application."""

    INVERTER = "inverter"
    BREAKER = "breaker"
    SENSOR = "sensor"
    BATTERY = "battery"
    UNKNOWN = "unknown"


class DeviceStatus(str, Enum):
    """Normalized connectivity or runtime state of a device."""

    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    FAULT = "fault"
    UNKNOWN = "unknown"
    ON = "on"
    OFF = "off"


class FaultSeverity(str, Enum):
    """Normalized impact level of a reported device fault."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class DeviceCapability(DomainModel):
    """Features confirmed to be supported by a device."""

    switching: bool = False
    instantaneous_power: bool = False
    voltage: bool = False
    current: bool = False
    energy_total: bool = False
    fault_monitoring: bool = False
    countdown: bool = False
    remote_configuration: bool = False


class DeviceFault(DomainModel):
    """A normalized warning or fault, independent of vendor error codes."""

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    severity: FaultSeverity
    active: bool = True
    occurred_at: datetime | None = None
    cleared_at: datetime | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class Device(DomainModel):
    """Common identity and current state for any managed energy device."""

    device_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    device_type: DeviceType = DeviceType.UNKNOWN
    status: DeviceStatus = DeviceStatus.UNKNOWN
    capabilities: DeviceCapability = Field(default_factory=DeviceCapability)
    manufacturer: str | None = None
    model: str | None = None
    serial_number: str | None = None
    last_seen_at: datetime | None = None
    faults: list[DeviceFault] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_online(self) -> bool:
        """Return whether the device currently has an available connection."""

        return self.status in {DeviceStatus.ONLINE, DeviceStatus.ON}


DeviceSnapshot = Device
