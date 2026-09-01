"""Normalized inverter, battery, grid, and photovoltaic status models."""

from __future__ import annotations

from enum import Enum

from pydantic import Field

from .device import DeviceFault, DeviceStatus, DomainModel
from .energy_reading import ElectricalMeasurement


class BatteryChargingState(str, Enum):
    """Normalized battery power-flow state."""

    CHARGING = "charging"
    DISCHARGING = "discharging"
    IDLE = "idle"
    UNKNOWN = "unknown"


class GridState(str, Enum):
    """Normalized grid availability state."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    UNSTABLE = "unstable"
    UNKNOWN = "unknown"


class BatteryStatus(DomainModel):
    """Current battery measurements and charging state."""

    voltage_volts: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    state_of_charge_percent: float | None = Field(
        default=None, ge=0, le=100, allow_inf_nan=False
    )
    current_amperes: float | None = Field(default=None, allow_inf_nan=False)
    charging_state: BatteryChargingState = BatteryChargingState.UNKNOWN


class GridStatus(DomainModel):
    """Current utility-grid availability and measurements."""

    state: GridState = GridState.UNKNOWN
    electrical: ElectricalMeasurement = Field(default_factory=ElectricalMeasurement)


class PVStatus(DomainModel):
    """Current photovoltaic input measurements."""

    electrical: ElectricalMeasurement = Field(default_factory=ElectricalMeasurement)


class InverterStatus(DomainModel):
    """Complete normalized operational snapshot of a hybrid inverter."""

    status: DeviceStatus = DeviceStatus.UNKNOWN
    operating_mode: str | None = None
    pv: PVStatus = Field(default_factory=PVStatus)
    output: ElectricalMeasurement = Field(default_factory=ElectricalMeasurement)
    grid: GridStatus = Field(default_factory=GridStatus)
    battery: BatteryStatus = Field(default_factory=BatteryStatus)
    load_percent: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    temperature_celsius: float | None = Field(default=None, allow_inf_nan=False)
    warnings: list[str] = Field(default_factory=list)
    faults: list[DeviceFault] = Field(default_factory=list)
