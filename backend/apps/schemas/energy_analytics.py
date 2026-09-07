"""Sanitized, database-backed energy summary schemas."""

from datetime import date
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class EnergyCoverageStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class EnergyMetricValues(BaseModel):
    generated_kwh: float | None = None
    consumed_kwh: float | None = None
    grid_imported_kwh: float | None = None


class EnergyMetricCoverage(BaseModel):
    generated: EnergyCoverageStatus
    consumption: EnergyCoverageStatus
    grid_import: EnergyCoverageStatus


class DailyEnergySummary(EnergyMetricValues):
    date: date
    status: EnergyCoverageStatus
    coverage: EnergyMetricCoverage


class EnergySummaryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    timezone: str
    from_: date = Field(serialization_alias="from")
    to: date
    totals: EnergyMetricValues
    status: EnergyCoverageStatus
    coverage: EnergyMetricCoverage
    days: list[DailyEnergySummary]
