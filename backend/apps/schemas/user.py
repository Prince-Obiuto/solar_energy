"""Secret-free user administration schemas."""

from pydantic import BaseModel, Field, field_validator

from apps.models import UserRole
from apps.schemas.auth import CurrentUser


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    full_name: str | None = Field(default=None, max_length=255)
    password: str = Field(min_length=12, max_length=1024)
    role: UserRole = UserRole.STUDENT

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized:
            raise ValueError("Invalid email address")
        return normalized


class UserUpdate(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None


class UserList(BaseModel):
    items: list[CurrentUser]
    total: int
