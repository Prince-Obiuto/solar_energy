"""Normalized inverter, battery, grid, and photovoltaic status models."""

from __future__ import annotations

from datetime import datetime
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


class InverterTelemetryStatus(DomainModel):
    """Verified normalized inverter output category."""

    status: str | None = None
    rated_power_w: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    output_voltage: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    output_frequency: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    output_power_w: float | None = Field(default=None, allow_inf_nan=False)
    load_percentage: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)


class BatteryTelemetryStatus(DomainModel):
    """Verified normalized battery category."""

    soc: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    voltage: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    charging_current: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    discharge_current: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    power_w: float | None = Field(default=None, allow_inf_nan=False)
    status: str | None = None
    charge_stage: str | None = None
    type: str | None = None


class SolarTelemetryStatus(DomainModel):
    """Verified normalized solar/PV category."""

    connected: str | None = None
    pv1_voltage: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    pv1_power_w: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    pv2_voltage: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    pv2_power_w: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    total_power_w: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    daily_energy_kwh: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    monthly_energy_kwh: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    total_energy_kwh: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class GridTelemetryStatus(DomainModel):
    """Verified normalized utility-grid category."""

    voltage: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    frequency: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    power_w: float | None = Field(default=None, allow_inf_nan=False)


class InverterTelemetry(DomainModel):
    """Read-only normalized telemetry snapshot from the deployed inverter."""

    timestamp: datetime
    inverter: InverterTelemetryStatus = Field(default_factory=InverterTelemetryStatus)
    battery: BatteryTelemetryStatus = Field(default_factory=BatteryTelemetryStatus)
    solar: SolarTelemetryStatus = Field(default_factory=SolarTelemetryStatus)
    grid: GridTelemetryStatus = Field(default_factory=GridTelemetryStatus)
