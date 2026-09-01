"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings for the FastAPI application."""

    app_name: str = "Smart Renewable Energy Management System"
    app_env: str = "development"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = Field(default="http://localhost:5173")

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


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()


settings = get_settings()
