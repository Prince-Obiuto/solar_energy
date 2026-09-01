"""Normalized domain models shared by APIs, realtime, and persistence layers."""

from .breaker import BreakerDevice, BreakerState, BreakerStatus
from .control_event import CommandResult, CommandStatus, DeviceCommand
from .device import (
    Device,
    DeviceCapability,
    DeviceFault,
    RegisteredDevice,
    DeviceSnapshot,
    DeviceStatus,
    DeviceType,
    DomainModel,
    FaultSeverity,
)
from .energy_reading import ElectricalMeasurement, EnergyMeasurement, EnergyReading
from .inverter import (
    BatteryChargingState,
    BatteryStatus,
    BatteryTelemetryStatus,
    GridTelemetryStatus,
    GridState,
    GridStatus,
    InverterStatus,
    InverterTelemetry,
    InverterTelemetryStatus,
    PVStatus,
    SolarTelemetryStatus,
)
from .user import UserProfile, UserRole

__all__ = [
    "BatteryChargingState", "BatteryStatus", "BatteryTelemetryStatus", "BreakerDevice",
    "BreakerState", "BreakerStatus",
    "CommandResult", "CommandStatus", "Device", "DeviceCapability", "DeviceCommand",
    "DeviceFault", "DeviceSnapshot", "DeviceStatus", "DeviceType", "DomainModel",
    "ElectricalMeasurement", "EnergyMeasurement", "EnergyReading", "FaultSeverity", "RegisteredDevice",
    "GridState", "GridStatus", "GridTelemetryStatus", "InverterStatus", "InverterTelemetry",
    "InverterTelemetryStatus", "PVStatus", "SolarTelemetryStatus", "UserProfile", "UserRole",
]
