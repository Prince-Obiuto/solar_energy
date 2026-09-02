"""Normalized smart battery load-management read models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class LoadManagementStage(str, Enum):
    NORMAL = "normal"
    CONSERVATION = "conservation"
    CRITICAL_CONSERVATION = "critical_conservation"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"


class PendingTransition(str, Enum):
    SHED = "shed"
    RESTORE = "restore"


class LoadPolicyStatus(BaseModel):
    policy_name: str
    breaker_id: str | None = None
    display_name: str
    area: str | None = None
    enabled: bool
    shed_soc: float
    restore_soc: float
    current_soc: float | None = None
    breaker_online: bool | None = None
    relay_on: bool | None = None
    automatically_shed: bool = False
    pending_transition: PendingTransition | None = None
    confirmation_count: int = Field(default=0, ge=0)
    confirmation_required: int = Field(ge=1)
    last_transition: str | None = None
    last_transition_at: datetime | None = None
    last_error: str | None = None


class LoadManagementStatus(BaseModel):
    enabled: bool
    active: bool
    current_soc: float | None = None
    current_stage: LoadManagementStage
    policies: list[LoadPolicyStatus]

