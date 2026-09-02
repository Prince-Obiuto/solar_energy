"""Authenticated read-only smart load-management status API."""

from fastapi import APIRouter, HTTPException, status

from apps.core.runtime import get_application_runtime
from apps.schemas.load_management import LoadManagementStatus

router = APIRouter()


@router.get("", response_model=LoadManagementStatus)
def get_load_management() -> LoadManagementStatus:
    runtime = get_application_runtime()
    if runtime is None or runtime.load_shedding_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Load management runtime is unavailable",
        )
    return runtime.load_shedding_service.get_status()
