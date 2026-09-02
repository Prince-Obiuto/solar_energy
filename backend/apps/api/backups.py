"""Administrator-only operational backup status routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from apps.core.permissions import require_admin
from apps.db.session import get_db
from apps.jobs.backup import list_backup_runs
from apps.models.persistence import BackupRunRecord
from apps.schemas.backup import BackupRunView, BackupStatusResponse


router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/status", response_model=BackupStatusResponse)
async def backup_status(
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_db),
) -> BackupStatusResponse:
    """Return the latest run and bounded recent backup history."""

    records = list_backup_runs(session, limit=limit)
    views = [BackupRunView.model_validate(record) for record in records]
    total = session.scalar(select(func.count()).select_from(BackupRunRecord)) or 0
    return BackupStatusResponse(
        current=views[0] if views else None,
        recent=views,
        total=total,
    )
