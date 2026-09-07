"""Unauthenticated but one-time-token-protected first-run setup routes."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from apps.core.config import settings
from apps.core.rate_limit import RateLimitExceeded, SlidingWindowRateLimiter
from apps.db.session import get_db
from apps.schemas.setup import (
    AdministratorSetupResponse,
    InitialAdministratorRequest,
    SetupCodeRequest,
    SetupProgress,
    SetupVerificationResponse,
)
from apps.services.setup_service import SetupLockedError, SetupService, SetupStateError

router = APIRouter()
setup_limiter = SlidingWindowRateLimiter(
    attempts=settings.login_rate_limit_attempts,
    window_seconds=settings.login_rate_limit_window_seconds,
)


def _rate_limit(request: Request, operation: str) -> str:
    client = request.client.host if request.client else "unknown"
    key = f"{operation}:{client}"
    try:
        setup_limiter.check(key)
    except RateLimitExceeded:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many setup attempts; try again later",
            headers={"Retry-After": str(settings.login_rate_limit_window_seconds)},
        ) from None
    return key


@router.get(
    "/status", response_model=SetupProgress, response_model_exclude_none=True
)
async def setup_status(session: Session = Depends(get_db)) -> SetupProgress:
    return SetupService(session).progress()


@router.post("/verify", response_model=SetupVerificationResponse)
async def verify_setup_code(
    payload: SetupCodeRequest,
    request: Request,
    session: Session = Depends(get_db),
) -> SetupVerificationResponse:
    key = _rate_limit(request, "verify")
    valid = SetupService(session).verify(payload.setup_code)
    if valid:
        setup_limiter.reset(key)
    return SetupVerificationResponse(valid=valid)


@router.post(
    "/administrator",
    status_code=status.HTTP_201_CREATED,
    response_model=AdministratorSetupResponse,
)
async def create_initial_administrator(
    payload: InitialAdministratorRequest,
    request: Request,
    session: Session = Depends(get_db),
) -> AdministratorSetupResponse:
    key = _rate_limit(request, "administrator")
    service = SetupService(session)
    try:
        user = service.create_administrator(
            code=payload.setup_code,
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
        )
    except SetupLockedError:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Installation setup is unavailable") from None
    except (SetupStateError, ValueError):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Administrator setup could not be completed") from None
    setup_limiter.reset(key)
    return AdministratorSetupResponse(**{
        "administrator": {
            "id": str(user.id), "email": user.email, "full_name": user.full_name,
            "role": user.role, "is_active": user.is_active,
        },
        "setup": service.progress(),
    })
