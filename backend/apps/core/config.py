"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings for the FastAPI application."""

    app_name: str = "Smart Renewable Energy Management System"
    app_env: str = "development"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = Field(default="http://localhost:5173")
    database_url: SecretStr = SecretStr("postgresql+psycopg://localhost/solar_energy")
    jwt_secret_key: SecretStr = SecretStr("development-only-change-me")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=60, gt=0, le=1440)
    initial_admin_email: str | None = None
    initial_admin_password: SecretStr | None = None
    initial_admin_full_name: str = "System Administrator"
    beve_poll_interval_seconds: float = Field(default=30, gt=0)
    tuya_poll_interval_seconds: float = Field(default=10, gt=0)
    tuya_control_verify_delay_seconds: float = Field(default=0.5, ge=0, le=10)
    telemetry_persist_interval_seconds: float = Field(default=60, gt=0)
    device_stale_after_seconds: float = Field(default=90, gt=0)
    telemetry_retry_attempts: int = Field(default=2, ge=1, le=5)
    telemetry_retry_delay_seconds: float = Field(default=1, ge=0)
    websocket_heartbeat_interval_seconds: float = Field(default=20, gt=0)
    websocket_stale_after_seconds: float = Field(default=60, gt=0)

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        """Return configured CORS origins as a normalized list."""

        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def require_production_jwt_secret(self) -> "Settings":
        if self.app_env.lower() not in {"development", "test"} and self.jwt_secret_key.get_secret_value() == "development-only-change-me":
            raise ValueError("JWT_SECRET_KEY must be configured outside development")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()


settings = get_settings()
