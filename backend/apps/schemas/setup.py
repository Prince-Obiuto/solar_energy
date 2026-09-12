"""Secret-safe first-run setup API schemas."""

from datetime import datetime
from typing import Literal

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
