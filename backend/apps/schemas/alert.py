"""Normalized alert lifecycle API schemas."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertView(BaseModel):
    id: UUID
    severity: AlertSeverity
    first_seen: datetime
    last_seen: datetime
    resolved_at: datetime | None = None
    acknowledged_at: datetime | None = None
    acknowledged_by: UUID | None = None
    device: str | None = None
    area: str | None = None
    category: str
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AlertList(BaseModel):
    items: list[AlertView]
    total: int
