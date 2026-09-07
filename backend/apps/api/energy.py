"""Unified read-only energy snapshot API routes."""

from datetime import date, datetime
from zoneinfo import ZoneInfo
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from apps.core.permissions import get_current_user
from apps.db.session import get_db
from apps.models.persistence import UserRecord
from apps.schemas.report import Aggregation, HistoryQuery, HistoryResponse, HistorySource
from apps.services.report_service import HistoryAccessError, HistoryService, enforce_history_access

from apps.services.energy_service import CurrentEnergySnapshot, list_energy_points
from apps.jobs.energy_collector import get_energy_collector
from apps.services.breaker_monitoring_service import BreakerMonitoringService
from apps.services.breaker_service import get_breaker_service
from apps.services.dashboard_service import DashboardService
from apps.schemas.energy_analytics import EnergySummaryResponse
from apps.services.energy_analytics_service import EnergyAnalyticsService

router = APIRouter()


def get_energy_analytics_service(
    session: Session = Depends(get_db),
) -> EnergyAnalyticsService:
    return EnergyAnalyticsService(session)


@router.get("/summary", response_model=EnergySummaryResponse)
async def energy_summary(
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = None,
    service: EnergyAnalyticsService = Depends(get_energy_analytics_service),
) -> EnergySummaryResponse:
    """Return sanitized daily system-energy totals from persisted telemetry."""

    today = datetime.now(ZoneInfo("Africa/Lagos")).date()
    if (from_ is None) != (to is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="from and to must be supplied together",
        )
    start = from_ or today
    end = to or today
    try:
        return service.summarize(start, end)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from None


@router.get("")
async def list_energy() -> dict[str, object]:
    """Compatibility read route until historical persistence is implemented."""

    points = list_energy_points()
    return {"items": points, "total": len(points)}


@router.get("/history", response_model=HistoryResponse)
async def energy_history(
    source: HistorySource,
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = None,
    device_id: str | None = None,
    area_id: UUID | None = None,
    aggregation: Aggregation = Aggregation.RAW,
    limit: int = Query(default=1000, ge=1, le=10000),
    user: UserRecord = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> HistoryResponse:
    if any(value is not None and (value.tzinfo is None or value.utcoffset() is None) for value in (from_, to)):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="History timestamps must include a timezone")
    if from_ and to and from_ >= to:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="from must be earlier than to")
    query = HistoryQuery(
        source=source, from_=from_, to=to, device_id=device_id,
        area_id=area_id, aggregation=aggregation, limit=limit,
    )
    try:
        enforce_history_access(user, query)
    except HistoryAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from None
    return HistoryService(session).query(query)


@router.get("/latest", response_model=CurrentEnergySnapshot)
async def latest_energy(
    session: Session = Depends(get_db),
) -> CurrentEnergySnapshot:
    collector = get_energy_collector()
    dashboard = await DashboardService(session, collector).get_dashboard()
    if dashboard.data_status.source_timestamp is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Current energy telemetry is unavailable",
        )
    breakers = await BreakerMonitoringService(
        session, get_breaker_service(), collector
    ).list_breakers()
    return CurrentEnergySnapshot(
        captured_at=dashboard.data_status.last_successful_poll_at or dashboard.data_status.source_timestamp,
        inverter=dashboard.inverter, battery=dashboard.battery,
        solar=dashboard.solar, grid=dashboard.grid, breakers=breakers,
    )
