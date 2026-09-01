"""Historical query, report, and export schemas."""

from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class HistorySource(str, Enum):
    SOLAR = "solar"
    INVERTER = "inverter"
    BATTERY = "battery"
    GRID = "grid"
    AREAS = "areas"


class Aggregation(str, Enum):
    RAW = "raw"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"


class ReportPeriod(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"


class HistoryQuery(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    source: HistorySource
    from_: datetime | None = Field(default=None, alias="from")
    to: datetime | None = None
    device_id: str | None = Field(default=None, min_length=1, max_length=255)
    area_id: UUID | None = None
    aggregation: Aggregation = Aggregation.RAW
    limit: int = Field(default=1000, ge=1, le=10000)

    @model_validator(mode="after")
    def valid_window(self) -> "HistoryQuery":
        for value in (self.from_, self.to):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError("History timestamps must include a timezone")
        if self.from_ and self.to and self.from_ >= self.to:
            raise ValueError("from must be earlier than to")
        return self


class HistoryPoint(BaseModel):
    timestamp: datetime
    source: HistorySource
    device_id: str
    area_id: UUID | None = None
    area: str | None = None
    metrics: dict[str, Any]


class HistoryResponse(BaseModel):
    source: HistorySource
    aggregation: Aggregation
    from_: datetime | None = Field(serialization_alias="from")
    to: datetime | None = None
    items: list[HistoryPoint]
    total: int


class ReportQuery(HistoryQuery):
    period: ReportPeriod = ReportPeriod.DAILY

    def resolved_window(self, now: datetime) -> tuple[datetime, datetime]:
        end = self.to or now
        if self.period is ReportPeriod.CUSTOM:
            if self.from_ is None or self.to is None:
                raise ValueError("Custom reports require from and to")
            return self.from_, self.to
        if self.period is ReportPeriod.DAILY:
            start = end.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        elif self.period is ReportPeriod.WEEKLY:
            start = end - timedelta(days=7)
        else:
            start = end.astimezone(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return start, end


class TechnicalReport(BaseModel):
    period: ReportPeriod
    generated_at: datetime
    from_: datetime = Field(serialization_alias="from")
    to: datetime
    history: HistoryResponse
