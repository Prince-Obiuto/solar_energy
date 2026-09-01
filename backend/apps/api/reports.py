"""Historical technical report and audited export routes."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from apps.core.permissions import get_current_user
from apps.db.session import get_db
from apps.models.persistence import UserRecord
from apps.schemas.report import (
    Aggregation, HistorySource, ReportPeriod, ReportQuery, TechnicalReport,
)
from apps.services.report_service import HistoryAccessError, ReportService

router = APIRouter()


def report_query(
    source: HistorySource = HistorySource.SOLAR,
    period: ReportPeriod = ReportPeriod.DAILY,
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = None,
    device_id: str | None = None,
    area_id: UUID | None = None,
    aggregation: Aggregation = Aggregation.HOUR,
    limit: int = Query(default=1000, ge=1, le=10000),
) -> ReportQuery:
    if any(value is not None and (value.tzinfo is None or value.utcoffset() is None) for value in (from_, to)):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="History timestamps must include a timezone")
    if from_ and to and from_ >= to:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="from must be earlier than to")
    return ReportQuery(
        source=source, period=period, from_=from_, to=to, device_id=device_id,
        area_id=area_id, aggregation=aggregation, limit=limit,
    )


def generate_report(service: ReportService, query: ReportQuery, user: UserRecord, *, audit: bool = True) -> TechnicalReport:
    try:
        return service.generate(query, user, audit=audit)
    except HistoryAccessError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from None


@router.get("", response_model=TechnicalReport)
async def get_report(
    query: ReportQuery = Depends(report_query),
    user: UserRecord = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> TechnicalReport:
    """Generate a bounded normalized report entirely from persistence."""

    return generate_report(ReportService(session), query, user)


@router.get("/export.csv")
async def export_csv(
    query: ReportQuery = Depends(report_query),
    user: UserRecord = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> Response:
    service = ReportService(session)
    report = generate_report(service, query, user, audit=False)
    content = service.export_csv(report, user, query)
    return Response(
        content=content, media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="energy-report.csv"'},
    )


@router.get("/export.pdf")
async def export_pdf(
    query: ReportQuery = Depends(report_query),
    user: UserRecord = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> Response:
    service = ReportService(session)
    report = generate_report(service, query, user, audit=False)
    content = service.export_pdf(report, user, query)
    return Response(
        content=content, media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="energy-report.pdf"'},
    )
