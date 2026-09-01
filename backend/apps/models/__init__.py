"""Normalized domain models shared by APIs, realtime, and persistence layers."""

from .breaker import BreakerState, BreakerStatus
from .control_event import CommandResult, CommandStatus, DeviceCommand
from .device import (
    Device,
    DeviceCapability,
    DeviceFault,
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
    GridState,
    GridStatus,
    InverterStatus,
    PVStatus,
)
from .user import UserProfile

__all__ = [
    "BatteryChargingState", "BatteryStatus", "BreakerState", "BreakerStatus",
    "CommandResult", "CommandStatus", "Device", "DeviceCapability", "DeviceCommand",
    "DeviceFault", "DeviceSnapshot", "DeviceStatus", "DeviceType", "DomainModel",
    "ElectricalMeasurement", "EnergyMeasurement", "EnergyReading", "FaultSeverity",
    "GridState", "GridStatus", "InverterStatus", "PVStatus", "UserProfile",
]
