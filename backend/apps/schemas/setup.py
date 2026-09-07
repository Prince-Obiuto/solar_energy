"""Secret-safe first-run setup API schemas."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


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
