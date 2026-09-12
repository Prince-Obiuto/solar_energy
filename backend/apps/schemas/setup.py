"""Secret-safe first-run setup API schemas."""

from datetime import datetime
from typing import Literal

import unicodedata

from pydantic import BaseModel, Field, SecretStr, field_validator


SetupStep = Literal["initialize", "administrator", "beve", "tuya", "devices", "confirm"]


class SetupCodeRequest(BaseModel):
    setup_code: str = Field(min_length=1, max_length=128)


class InitialAdministratorRequest(SetupCodeRequest):
    email: str = Field(min_length=3, max_length=320)
    full_name: str | None = Field(default=None, max_length=255)
    password: str = Field(min_length=12, max_length=1024)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized:
            raise ValueError("Invalid email address")
        return normalized


class SetupProgress(BaseModel):
    setup_required: bool
    setup_completed: bool
    setup_initialized: bool | None = None
    admin_configured: bool | None = None
    beve_configured: bool | None = None
    tuya_configured: bool | None = None
    devices_verified: bool | None = None
    next_step: SetupStep | None = None


class SetupVerificationResponse(BaseModel):
    valid: bool


class SetupAdministrator(BaseModel):
    id: str
    email: str
    full_name: str | None = None
    role: str
    is_active: bool


class AdministratorSetupResponse(BaseModel):
    administrator: SetupAdministrator
    setup: SetupProgress


BeveSetupErrorCategory = Literal[
    "authentication_failed",
    "device_not_found",
    "network_error",
    "timeout",
    "malformed_response",
    "configuration_invalid",
    "vendor_error",
]


class BeveSetupRequest(SetupCodeRequest):
    username: SecretStr = Field(min_length=1, max_length=320)
    password: SecretStr = Field(min_length=1, max_length=1024)
    station_id: str = Field(min_length=1, max_length=255)
    device_id: str = Field(min_length=1, max_length=255)

    @field_validator("station_id", "device_id")
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Identifier cannot be blank")
        return normalized


class BeveVerificationSummary(BaseModel):
    station_device_matched: bool
    inverter_status: str | None = None
    battery_soc: float | None = None
    output_power_w: float | None = None
    pv_status: str | None = None
    source_timestamp: datetime | None = None


class BeveVerificationResult(BaseModel):
    success: bool
    device_verified: bool
    category: BeveSetupErrorCategory | None = None
    message: str
    summary: BeveVerificationSummary | None = None


class BeveConfigurationResponse(BaseModel):
    verification: BeveVerificationResult
    setup: SetupProgress
    runtime_activation: Literal["restart_required"] = "restart_required"


TuyaSetupErrorCategory = Literal[
    "cloud_authentication_failed",
    "cloud_device_fetch_failed",
    "cloud_configuration_invalid",
    "network_error",
    "timeout",
    "cloud_malformed_response",
    "scan_timeout",
    "no_devices_found",
    "onboarding_session_invalid",
    "device_not_on_lan",
    "device_id_mismatch",
    "local_connection_failed",
    "protocol_error",
    "malformed_response",
    "unsupported_device",
    "configuration_invalid",
]


class TuyaCloudSetupRequest(SetupCodeRequest):
    region: str = Field(min_length=1, max_length=10)
    access_id: SecretStr = Field(min_length=1, max_length=255)
    access_secret: SecretStr = Field(min_length=1, max_length=1024)
    anchor_device_id: SecretStr | None = None


class TuyaCloudCandidateResponse(BaseModel):
    device_ref: str
    name: str | None = None
    product_id: str | None = None
    category: str | None = None
    model: str | None = None
    online: bool | None = None
    local_configuration_available: bool


class TuyaCloudDiscoveryResponse(BaseModel):
    success: bool
    category: TuyaSetupErrorCategory | None = None
    message: str
    onboarding_session: str | None = None
    devices: list[TuyaCloudCandidateResponse] = Field(default_factory=list)


class TuyaOnboardingSessionRequest(SetupCodeRequest):
    onboarding_session: SecretStr = Field(min_length=32, max_length=256)


class TuyaMatchedDeviceResponse(BaseModel):
    device_ref: str
    name: str | None = None
    ip_address: str
    protocol_version: str | None = None
    product_id: str | None = None
    compatible: bool | None = None
    local_configuration_available: bool


class TuyaScanResponse(BaseModel):
    success: bool
    category: TuyaSetupErrorCategory | None = None
    message: str
    matched: list[TuyaMatchedDeviceResponse] = Field(default_factory=list)
    cloud_only: list[str] = Field(default_factory=list)
    lan_only_count: int = 0


class TuyaDeviceSelection(BaseModel):
    device_ref: str = Field(min_length=16, max_length=256)
    friendly_name: str = Field(min_length=1, max_length=120)
    area: str = Field(min_length=1, max_length=120)

    @field_validator("friendly_name", "area")
    @classmethod
    def validate_label(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or any(unicodedata.category(character) == "Cc" for character in normalized):
            raise ValueError("Name and area must be printable text")
        return normalized


class TuyaDeviceConfigurationRequest(TuyaOnboardingSessionRequest):
    devices: list[TuyaDeviceSelection] = Field(min_length=1, max_length=100)


class TuyaDeviceVerificationResponse(BaseModel):
    device_ref: str
    friendly_name: str
    area: str
    verified: bool
    connectivity: Literal["online", "unavailable"]
    relay_state: bool | None = None
    voltage_v: float | None = None
    current_a: float | None = None
    power_w: float | None = None
    protocol_version: str | None = None
    category: TuyaSetupErrorCategory | None = None
    message: str | None = None


class TuyaDeviceConfigurationResponse(BaseModel):
    success: bool
    category: TuyaSetupErrorCategory | None = None
    message: str
    devices: list[TuyaDeviceVerificationResponse] = Field(default_factory=list)
    setup: SetupProgress
    runtime_activation: Literal["restart_required"] | None = None


class TuyaConfiguredDeviceSummary(BaseModel):
    friendly_name: str
    area: str


class TuyaConfigurationStatusResponse(BaseModel):
    configured: bool
    devices_verified: bool
    configured_device_count: int
    devices: list[TuyaConfiguredDeviceSummary] = Field(default_factory=list)
