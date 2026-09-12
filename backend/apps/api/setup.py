"""Unauthenticated but one-time-token-protected first-run setup routes."""

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from apps.core.config import settings
from apps.core.rate_limit import RateLimitExceeded, SlidingWindowRateLimiter
from apps.db.session import get_db
from apps.integrations.inverter import BeveClient, BeveConfig
from apps.integrations.tuya import TuyaClient, TuyaDeviceConfig
from apps.integrations.tuya.onboarding import TinyTuyaCloudGateway, TinyTuyaLanDiscovery
from apps.schemas.setup import (
    AdministratorSetupResponse,
    BeveConfigurationResponse,
    BeveSetupRequest,
    BeveVerificationResult,
    InitialAdministratorRequest,
    SetupCodeRequest,
    SetupProgress,
    SetupVerificationResponse,
    TuyaCloudDiscoveryResponse,
    TuyaCloudSetupRequest,
    TuyaConfigurationStatusResponse,
    TuyaDeviceConfigurationRequest,
    TuyaDeviceConfigurationResponse,
    TuyaOnboardingSessionRequest,
    TuyaScanResponse,
)
from apps.services.beve_setup_service import BeveSetupService
from apps.services.runtime_configuration_service import RuntimeConfigurationService
from apps.services.setup_service import SetupLockedError, SetupService, SetupStateError
from apps.services.tuya_onboarding_store import TuyaOnboardingStore
from apps.services.tuya_setup_service import TuyaScanInProgressError, TuyaSetupService

router = APIRouter()
setup_limiter = SlidingWindowRateLimiter(
    attempts=settings.login_rate_limit_attempts,
    window_seconds=settings.login_rate_limit_window_seconds,
)
tuya_onboarding_store = TuyaOnboardingStore(
    ttl_seconds=settings.tuya_onboarding_session_ttl_seconds,
    max_sessions=settings.tuya_onboarding_max_sessions,
)


def get_beve_setup_client_factory() -> Callable[[BeveConfig], object]:
    """Provide the same read-only BEVE client used by normal runtime composition."""

    return BeveClient


def get_runtime_configuration_service(
    session: Session = Depends(get_db),
) -> RuntimeConfigurationService:
    return RuntimeConfigurationService(session)


def get_tuya_onboarding_store() -> TuyaOnboardingStore:
    return tuya_onboarding_store


def get_tuya_cloud_gateway() -> TinyTuyaCloudGateway:
    return TinyTuyaCloudGateway()


def get_tuya_lan_discovery() -> TinyTuyaLanDiscovery:
    return TinyTuyaLanDiscovery()


def get_tuya_setup_client_factory() -> Callable[[TuyaDeviceConfig], object]:
    def factory(config: TuyaDeviceConfig) -> TuyaClient:
        return TuyaClient(
            config,
            max_attempts=settings.telemetry_retry_attempts,
            socket_timeout_seconds=settings.tuya_socket_timeout_seconds,
            retry_delay_seconds=settings.telemetry_retry_delay_seconds,
        )

    return factory


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


def _tuya_setup_service(
    session: Session,
    runtime_configuration: RuntimeConfigurationService,
    onboarding_store: TuyaOnboardingStore,
    cloud_gateway: TinyTuyaCloudGateway,
    lan_discovery: TinyTuyaLanDiscovery,
    client_factory: Callable[[TuyaDeviceConfig], object],
) -> TuyaSetupService:
    return TuyaSetupService(
        session,
        runtime_configuration,
        onboarding_store,
        cloud_gateway=cloud_gateway,
        lan_discovery=lan_discovery,
        client_factory=client_factory,
    )


@router.post("/tuya/cloud", response_model=TuyaCloudDiscoveryResponse)
def retrieve_tuya_cloud_devices(
    payload: TuyaCloudSetupRequest,
    request: Request,
    session: Session = Depends(get_db),
    runtime_configuration: RuntimeConfigurationService = Depends(
        get_runtime_configuration_service
    ),
    onboarding_store: TuyaOnboardingStore = Depends(get_tuya_onboarding_store),
    cloud_gateway: TinyTuyaCloudGateway = Depends(get_tuya_cloud_gateway),
    lan_discovery: TinyTuyaLanDiscovery = Depends(get_tuya_lan_discovery),
    client_factory: Callable[[TuyaDeviceConfig], object] = Depends(
        get_tuya_setup_client_factory
    ),
) -> TuyaCloudDiscoveryResponse:
    key = _rate_limit(request, "tuya-cloud")
    try:
        result = _tuya_setup_service(
            session,
            runtime_configuration,
            onboarding_store,
            cloud_gateway,
            lan_discovery,
            client_factory,
        ).retrieve_cloud_devices(payload)
    except SetupLockedError:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Installation setup is unavailable",
        ) from None
    except SetupStateError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tuya setup authorization failed",
        ) from None
    if result.success:
        setup_limiter.reset(key)
    return result


@router.post("/tuya/scan", response_model=TuyaScanResponse)
def scan_tuya_lan(
    payload: TuyaOnboardingSessionRequest,
    request: Request,
    session: Session = Depends(get_db),
    runtime_configuration: RuntimeConfigurationService = Depends(
        get_runtime_configuration_service
    ),
    onboarding_store: TuyaOnboardingStore = Depends(get_tuya_onboarding_store),
    cloud_gateway: TinyTuyaCloudGateway = Depends(get_tuya_cloud_gateway),
    lan_discovery: TinyTuyaLanDiscovery = Depends(get_tuya_lan_discovery),
    client_factory: Callable[[TuyaDeviceConfig], object] = Depends(
        get_tuya_setup_client_factory
    ),
) -> TuyaScanResponse:
    key = _rate_limit(request, "tuya-scan")
    try:
        result = _tuya_setup_service(
            session,
            runtime_configuration,
            onboarding_store,
            cloud_gateway,
            lan_discovery,
            client_factory,
        ).scan_lan(
            payload.setup_code,
            payload.onboarding_session.get_secret_value(),
        )
    except SetupLockedError:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Installation setup is unavailable",
        ) from None
    except SetupStateError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tuya setup authorization failed",
        ) from None
    except TuyaScanInProgressError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A Tuya LAN scan is already in progress",
        ) from None
    if result.success:
        setup_limiter.reset(key)
    return result


@router.post("/tuya/status", response_model=TuyaConfigurationStatusResponse)
def tuya_configuration_status(
    payload: SetupCodeRequest,
    request: Request,
    session: Session = Depends(get_db),
    runtime_configuration: RuntimeConfigurationService = Depends(
        get_runtime_configuration_service
    ),
    onboarding_store: TuyaOnboardingStore = Depends(get_tuya_onboarding_store),
    cloud_gateway: TinyTuyaCloudGateway = Depends(get_tuya_cloud_gateway),
    lan_discovery: TinyTuyaLanDiscovery = Depends(get_tuya_lan_discovery),
    client_factory: Callable[[TuyaDeviceConfig], object] = Depends(
        get_tuya_setup_client_factory
    ),
) -> TuyaConfigurationStatusResponse:
    key = _rate_limit(request, "tuya-status")
    try:
        result = _tuya_setup_service(
            session,
            runtime_configuration,
            onboarding_store,
            cloud_gateway,
            lan_discovery,
            client_factory,
        ).configuration_status(payload.setup_code)
    except SetupLockedError:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Installation setup is unavailable",
        ) from None
    except SetupStateError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tuya setup authorization failed",
        ) from None
    setup_limiter.reset(key)
    return result


@router.post("/tuya/devices", response_model=TuyaDeviceConfigurationResponse)
def configure_tuya_devices(
    payload: TuyaDeviceConfigurationRequest,
    request: Request,
    session: Session = Depends(get_db),
    runtime_configuration: RuntimeConfigurationService = Depends(
        get_runtime_configuration_service
    ),
    onboarding_store: TuyaOnboardingStore = Depends(get_tuya_onboarding_store),
    cloud_gateway: TinyTuyaCloudGateway = Depends(get_tuya_cloud_gateway),
    lan_discovery: TinyTuyaLanDiscovery = Depends(get_tuya_lan_discovery),
    client_factory: Callable[[TuyaDeviceConfig], object] = Depends(
        get_tuya_setup_client_factory
    ),
) -> TuyaDeviceConfigurationResponse:
    key = _rate_limit(request, "tuya-devices")
    try:
        result = _tuya_setup_service(
            session,
            runtime_configuration,
            onboarding_store,
            cloud_gateway,
            lan_discovery,
            client_factory,
        ).configure_devices(payload)
    except SetupLockedError:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Installation setup is unavailable",
        ) from None
    except SetupStateError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tuya setup authorization failed",
        ) from None
    if result.success:
        setup_limiter.reset(key)
    return result
