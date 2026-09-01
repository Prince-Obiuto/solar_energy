"""Authentication request and response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from apps.models import UserRole


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized:
            raise ValueError("Invalid email address")
        return normalized


class AccessToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class CurrentUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str | None = None
    role: UserRole
    is_active: bool
