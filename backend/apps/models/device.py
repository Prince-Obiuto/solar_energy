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


class ConnectivityType(str, Enum):
    CLOUD = "cloud"
    LOCAL = "local"


class DataSource(str, Enum):
    BEVE_CLOUD = "beve_cloud"
    TINYTUYA = "tinytuya"


class SourceStatus(str, Enum):
    CONNECTED = "connected"
    AUTHENTICATION_FAILED = "authentication_failed"
    TIMEOUT = "timeout"
    UNREACHABLE = "unreachable"
    CLOUD_ERROR = "cloud_error"
    UNKNOWN = "unknown"


class DataFreshness(str, Enum):
    LIVE = "live"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class DataStatus(DomainModel):
    """Availability of a telemetry source without inferring physical device state."""

    connectivity_type: ConnectivityType
    data_source: DataSource
    available: bool = False
    stale: bool = True
    source_status: SourceStatus = SourceStatus.UNKNOWN
    data_freshness: DataFreshness = DataFreshness.UNAVAILABLE
    last_successful_update: datetime | None = None
    last_attempt_at: datetime | None = None
    last_successful_poll_at: datetime | None = None
    source_timestamp: datetime | None = None
    source_changed: bool | None = None
    source_age_seconds: float | None = Field(default=None, ge=0)
    last_failure_category: str | None = None


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


class RegisteredDevice(DomainModel):
    """Secret-free device catalogue entry exposed by application services."""

    id: str = Field(min_length=1)
    friendly_name: str = Field(min_length=1)
    type: DeviceType
    area: str = Field(min_length=1)
    online: bool | None
    last_seen: datetime | None = None
    connectivity_type: ConnectivityType
    data_source: DataSource
    data_status: DataStatus
    relay_on: bool | None = None
    capabilities: DeviceCapability = Field(default_factory=DeviceCapability)
