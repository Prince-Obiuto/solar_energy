"""Normalized device command and result models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field

from .device import DomainModel


class CommandStatus(str, Enum):
    """Lifecycle state of a device command."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REJECTED = "rejected"
    TIMED_OUT = "timed_out"


class DeviceCommand(DomainModel):
    """Vendor-neutral request to perform an operation on a device."""

    command_id: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    command: str = Field(min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    requested_at: datetime


class CommandResult(DomainModel):
    """Normalized result returned by a command execution boundary."""

    command_id: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    status: CommandStatus
    completed_at: datetime | None = None
    message: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
