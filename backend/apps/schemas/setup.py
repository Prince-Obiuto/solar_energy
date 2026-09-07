"""Secret-safe first-run setup API schemas."""
from pydantic import BaseModel, Field, field_validator

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
