"""Normalized electrical and energy measurement models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from .device import DomainModel


class ElectricalMeasurement(DomainModel):
    """Instantaneous electrical measurements in standard SI-derived units."""

    voltage_volts: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    current_amperes: float | None = Field(default=None, allow_inf_nan=False)
    active_power_watts: float | None = Field(default=None, allow_inf_nan=False)
    apparent_power_va: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    frequency_hz: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    power_factor: float | None = Field(default=None, ge=-1, le=1, allow_inf_nan=False)


class EnergyMeasurement(DomainModel):
    """Cumulative energy counters; unsupported counters remain ``None``."""

    total_kwh: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    imported_kwh: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    exported_kwh: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    generated_kwh: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    consumed_kwh: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class EnergyReading(DomainModel):
    """Timestamped measurements from a normalized source."""

    source: str = Field(min_length=1)
    timestamp: datetime
    electrical: ElectricalMeasurement = Field(default_factory=ElectricalMeasurement)
    energy: EnergyMeasurement = Field(default_factory=EnergyMeasurement)
    metadata: dict[str, Any] = Field(default_factory=dict)
