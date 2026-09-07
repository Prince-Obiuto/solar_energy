"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime settings for the FastAPI application."""

    app_name: str = "Smart Renewable Energy Management System"
    app_env: str = "development"
    app_version: str = "0.1.0"
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = Field(default="http://localhost:5173")
    allowed_hosts: str = "localhost,127.0.0.1,testserver"
    log_level: str = "INFO"
    max_request_body_bytes: int = Field(default=1_048_576, ge=1024, le=10_485_760)
    login_rate_limit_attempts: int = Field(default=5, ge=1, le=100)
    login_rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)
    database_url: SecretStr = SecretStr("postgresql+psycopg://localhost/solar_energy")
    runtime_master_key_file: Path | None = None
    jwt_secret_key: SecretStr = SecretStr("development-only-change-me")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=60, gt=0, le=1440)
    initial_admin_email: str | None = None
    initial_admin_password: SecretStr | None = None
    initial_admin_full_name: str = "System Administrator"
    beve_poll_interval_seconds: float = Field(default=30, gt=0)
    beve_poll_stale_after_seconds: float = Field(default=90, gt=0)
    beve_source_stale_after_seconds: float = Field(default=900, gt=0)
    tuya_poll_interval_seconds: float = Field(default=10, gt=0)
    tuya_device_file: Path = Path("devices.json")
    tuya_socket_timeout_seconds: float = Field(default=5, gt=0, le=60)
    tuya_control_verify_delay_seconds: float = Field(default=0.5, ge=0, le=10)
    telemetry_persist_interval_seconds: float = Field(default=60, gt=0)
    energy_max_integration_gap_seconds: float = Field(default=900, gt=0)
    device_stale_after_seconds: float = Field(default=90, gt=0)
    telemetry_retry_attempts: int = Field(default=2, ge=1, le=5)
    telemetry_retry_delay_seconds: float = Field(default=1, ge=0)
    websocket_heartbeat_interval_seconds: float = Field(default=20, gt=0)
    websocket_stale_after_seconds: float = Field(default=60, gt=0)
    health_monitor_interval_seconds: float = Field(default=30, gt=0)
    alert_low_voltage_v: float | None = Field(default=None, ge=0)
    alert_high_voltage_v: float | None = Field(default=None, ge=0)
    alert_high_current_a: float | None = Field(default=None, ge=0)
    alert_high_power_w: float | None = Field(default=None, ge=0)
    backup_destination: Path = BACKEND_DIR / "backups"
    backup_secondary_destination: Path | None = None
    backup_retention_days: int = Field(default=30, ge=1, le=3650)
    backup_command: str = "pg_dump"
    backup_timeout_seconds: int = Field(default=3600, ge=60, le=86400)
    beve_username: SecretStr | None = None
    beve_password: SecretStr | None = None
    beve_base_url: str = "https://solar.siseli.com"
    beve_station_id: str | None = None
    beve_device_id: str | None = None
    beve_time_zone: str = "Africa/Lagos"
    beve_timeout_seconds: float = Field(default=30, gt=0, le=120)
    load_shedding_enabled: bool = True
    load_shedding_confirm_readings: int = Field(default=2, ge=1, le=20)
    load_shedding_lecturer_breaker_id: str | None = None
    load_shedding_lecturer_shed_soc: float = Field(default=20, ge=0, le=100)
    load_shedding_lecturer_restore_soc: float = Field(default=22, ge=0, le=100)
    load_shedding_admin_breaker_id: str | None = None
    load_shedding_admin_shed_soc: float = Field(default=15, ge=0, le=100)
    load_shedding_admin_restore_soc: float = Field(default=17, ge=0, le=100)

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        """Return configured CORS origins as a normalized list."""

        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_host_list(self) -> list[str]:
        return [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]

    @property
    def runtime_master_key_path(self) -> Path | None:
        """Resolve a configured key path relative to the backend directory."""

        if self.runtime_master_key_file is None:
            return None
        path = self.runtime_master_key_file
        return path if path.is_absolute() else (BACKEND_DIR / path).resolve()

    @model_validator(mode="after")
    def require_production_jwt_secret(self) -> "Settings":
        if self.app_env.lower() not in {"development", "test"}:
            if self.jwt_secret_key.get_secret_value() == "development-only-change-me":
                raise ValueError("JWT_SECRET_KEY must be configured outside development")
            if "*" in self.cors_origin_list:
                raise ValueError("Wildcard CORS origins are not allowed outside development")
        return self

    @model_validator(mode="after")
    def validate_voltage_thresholds(self) -> "Settings":
        if self.alert_low_voltage_v is not None and self.alert_high_voltage_v is not None and self.alert_low_voltage_v >= self.alert_high_voltage_v:
            raise ValueError("ALERT_LOW_VOLTAGE_V must be lower than ALERT_HIGH_VOLTAGE_V")
        return self

    @model_validator(mode="after")
    def validate_load_shedding_thresholds(self) -> "Settings":
        pairs = (
            (self.load_shedding_lecturer_shed_soc, self.load_shedding_lecturer_restore_soc, "LECTURER"),
            (self.load_shedding_admin_shed_soc, self.load_shedding_admin_restore_soc, "ADMIN"),
        )
        for shed, restore, name in pairs:
            if shed >= restore:
                raise ValueError(
                    f"LOAD_SHEDDING_{name}_SHED_SOC must be lower than its restore threshold"
                )
        return self

    @field_validator(
        "load_shedding_lecturer_breaker_id", "load_shedding_admin_breaker_id", mode="before"
    )
    @classmethod
    def normalize_optional_breaker_id(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()


settings = get_settings()
