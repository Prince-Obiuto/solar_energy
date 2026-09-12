"""Unauthenticated but one-time-token-protected first-run setup routes."""

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from apps.core.config import settings
from apps.core.rate_limit import RateLimitExceeded, SlidingWindowRateLimiter
from apps.db.session import get_db
from apps.integrations.inverter import BeveClient, BeveConfig
from apps.schemas.setup import (
    AdministratorSetupResponse,
    BeveConfigurationResponse,
    BeveSetupRequest,
    BeveVerificationResult,
    InitialAdministratorRequest,
    SetupCodeRequest,
    SetupProgress,
    SetupVerificationResponse,
)
from apps.services.beve_setup_service import BeveSetupService
from apps.services.runtime_configuration_service import RuntimeConfigurationService
from apps.services.setup_service import SetupLockedError, SetupService, SetupStateError

router = APIRouter()
setup_limiter = SlidingWindowRateLimiter(
    attempts=settings.login_rate_limit_attempts,
    window_seconds=settings.login_rate_limit_window_seconds,
)


def get_beve_setup_client_factory() -> Callable[[BeveConfig], object]:
    """Provide the same read-only BEVE client used by normal runtime composition."""

    return BeveClient


def get_runtime_configuration_service(
    session: Session = Depends(get_db),
) -> RuntimeConfigurationService:
    return RuntimeConfigurationService(session)


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


@router.post("/beve/test", response_model=BeveVerificationResult)
async def test_beve_configuration(
    payload: BeveSetupRequest,
    request: Request,
    session: Session = Depends(get_db),
    runtime_configuration: RuntimeConfigurationService = Depends(
        get_runtime_configuration_service
    ),
    client_factory: Callable[[BeveConfig], object] = Depends(
        get_beve_setup_client_factory
    ),
) -> BeveVerificationResult:
    key = _rate_limit(request, "beve-test")
    try:
        result = BeveSetupService(
            session,
            runtime_configuration,
            client_factory=client_factory,
        ).test_configuration(payload)
    except SetupLockedError:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Installation setup is unavailable",
        ) from None
    except SetupStateError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="BEVE setup authorization failed",
        ) from None
    if result.success:
        setup_limiter.reset(key)
    return result


@router.post("/beve", response_model=BeveConfigurationResponse)
async def configure_beve(
    payload: BeveSetupRequest,
    request: Request,
    session: Session = Depends(get_db),
    runtime_configuration: RuntimeConfigurationService = Depends(
        get_runtime_configuration_service
    ),
    client_factory: Callable[[BeveConfig], object] = Depends(
        get_beve_setup_client_factory
    ),
) -> BeveConfigurationResponse:
    key = _rate_limit(request, "beve-configure")
    try:
        result = BeveSetupService(
            session,
            runtime_configuration,
            client_factory=client_factory,
        ).configure(payload)
    except SetupLockedError:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Installation setup is unavailable",
        ) from None
    except SetupStateError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="BEVE setup authorization failed",
        ) from None
    if result.verification.success:
        setup_limiter.reset(key)
    return result
