"""Validated normalized breaker-control requests and results."""

from enum import Enum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from apps.models.control_event import CommandResult, CommandStatus, DeviceCommand

__all__ = ["CommandResult", "CommandStatus", "DeviceCommand"]


class RelayRestoreMode(str, Enum):
    OFF = "off"
    ON = "on"
    MEMORY = "memory"


class IndicatorMode(str, Enum):
    RELAY = "relay"
    POS = "pos"
    NONE = "none"
    ON = "on"


class ControlRequest(BaseModel):
    request_id: UUID
    reason: str | None = Field(default=None, max_length=500)


class SwitchRequest(ControlRequest):
    state: bool
    confirmed: Literal[True]
    reason: str = Field(min_length=5, max_length=500)


class CountdownRequest(ControlRequest):
    seconds: int = Field(ge=0, le=86400)


class RelayRestoreModeRequest(ControlRequest):
    mode: RelayRestoreMode


class IndicatorModeRequest(ControlRequest):
    mode: IndicatorMode


class ChildLockRequest(ControlRequest):
    enabled: bool


__all__ += [
    "ChildLockRequest", "ControlRequest", "CountdownRequest", "IndicatorMode",
    "IndicatorModeRequest", "RelayRestoreMode", "RelayRestoreModeRequest", "SwitchRequest",
]
