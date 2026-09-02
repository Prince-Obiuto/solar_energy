"""Operational backup status and history schemas."""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BackupStatus(str, Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class BackupRunView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: BackupStatus
    started_at: datetime
    finished_at: datetime | None = None
    output_size_bytes: int | None = None
    filename: str | None = None
    destination: str
    error_information: str | None = None


class BackupStatusResponse(BaseModel):
    current: BackupRunView | None = None
    recent: list[BackupRunView] = Field(default_factory=list)
    total: int = Field(ge=0)
