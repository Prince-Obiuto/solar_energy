"""SQLAlchemy persistence records for devices, telemetry, events, and alerts."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.db.base import Base, UTCDateTime


JSON_DATA = JSON().with_variant(JSONB(), "postgresql")
READING_ID = BigInteger().with_variant(Integer(), "sqlite")


def utc_now() -> datetime:
    return datetime.now(UTC)


class AreaRecord(Base):
    __tablename__ = "areas"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now, server_default=func.now()
    )

    devices: Mapped[list[DeviceRecord]] = relationship(back_populates="area")


class DeviceRecord(Base):
    __tablename__ = "devices"
    __table_args__ = (
        UniqueConstraint("external_reference", name="uq_devices_external_reference"),
        Index("ix_devices_area_type", "area_id", "device_type"),
        Index("ix_devices_enabled_type", "enabled", "device_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    external_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    friendly_name: Mapped[str] = mapped_column(String(255), nullable=False)
    device_type: Mapped[str] = mapped_column(String(50), nullable=False)
    area_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("areas.id", ondelete="SET NULL"), nullable=True
    )
    manufacturer: Mapped[str | None] = mapped_column(String(120))
    model: Mapped[str | None] = mapped_column(String(120))
    protocol: Mapped[str | None] = mapped_column(String(50))
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    last_seen: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now, server_default=func.now()
    )

    area: Mapped[AreaRecord | None] = relationship(back_populates="devices")


class UserRecord(Base):
    __tablename__ = "users"
    __table_args__ = (Index("ix_users_role_active", "role", "is_active"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(255))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="student")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now, server_default=func.now())


class InstallationStateRecord(Base):
    """Singleton progress record for secure first-run installation."""

    __tablename__ = "installation_state"
    __table_args__ = (CheckConstraint("id = 1", name="ck_installation_state_singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    setup_initialized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    admin_configured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    beve_configured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    tuya_configured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    devices_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    setup_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    setup_token_hash: Mapped[str | None] = mapped_column(String(255))
    installation_version: Mapped[str | None] = mapped_column(String(50))
    initialized_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    admin_configured_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now, server_default=func.now()
    )


class ReadingMixin:
    id: Mapped[int] = mapped_column(READING_ID, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )


class InverterReadingRecord(ReadingMixin, Base):
    __tablename__ = "inverter_readings"
    __table_args__ = (
        Index("ix_inverter_readings_device_timestamp", "device_id", "timestamp"),
        Index("ix_inverter_readings_timestamp", "timestamp"),
    )

    status: Mapped[str | None] = mapped_column(String(120))
    rated_power_w: Mapped[float | None] = mapped_column(Float)
    output_voltage: Mapped[float | None] = mapped_column(Float)
    output_frequency: Mapped[float | None] = mapped_column(Float)
    output_power_w: Mapped[float | None] = mapped_column(Float)
    load_percentage: Mapped[float | None] = mapped_column(Float)


class BatteryReadingRecord(ReadingMixin, Base):
    __tablename__ = "battery_readings"
    __table_args__ = (
        Index("ix_battery_readings_device_timestamp", "device_id", "timestamp"),
        Index("ix_battery_readings_timestamp", "timestamp"),
    )

    soc: Mapped[float | None] = mapped_column(Float)
    voltage: Mapped[float | None] = mapped_column(Float)
    charging_current: Mapped[float | None] = mapped_column(Float)
    discharge_current: Mapped[float | None] = mapped_column(Float)
    power_w: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str | None] = mapped_column(String(120))
    charge_stage: Mapped[str | None] = mapped_column(String(120))
    battery_type: Mapped[str | None] = mapped_column(String(120))


class SolarReadingRecord(ReadingMixin, Base):
    __tablename__ = "solar_readings"
    __table_args__ = (
        Index("ix_solar_readings_device_timestamp", "device_id", "timestamp"),
        Index("ix_solar_readings_timestamp", "timestamp"),
    )

    connected: Mapped[str | None] = mapped_column(String(120))
    pv1_voltage: Mapped[float | None] = mapped_column(Float)
    pv1_power_w: Mapped[float | None] = mapped_column(Float)
    pv2_voltage: Mapped[float | None] = mapped_column(Float)
    pv2_power_w: Mapped[float | None] = mapped_column(Float)
    total_power_w: Mapped[float | None] = mapped_column(Float)
    daily_energy_kwh: Mapped[float | None] = mapped_column(Float)
    monthly_energy_kwh: Mapped[float | None] = mapped_column(Float)
    total_energy_kwh: Mapped[float | None] = mapped_column(Float)


class GridReadingRecord(ReadingMixin, Base):
    __tablename__ = "grid_readings"
    __table_args__ = (
        Index("ix_grid_readings_device_timestamp", "device_id", "timestamp"),
        Index("ix_grid_readings_timestamp", "timestamp"),
    )

    voltage: Mapped[float | None] = mapped_column(Float)
    frequency: Mapped[float | None] = mapped_column(Float)
    power_w: Mapped[float | None] = mapped_column(Float)


class BreakerReadingRecord(ReadingMixin, Base):
    __tablename__ = "breaker_readings"
    __table_args__ = (
        Index("ix_breaker_readings_device_timestamp", "device_id", "timestamp"),
        Index("ix_breaker_readings_timestamp", "timestamp"),
        Index("ix_breaker_readings_online_timestamp", "online", "timestamp"),
    )

    online: Mapped[bool] = mapped_column(Boolean, nullable=False)
    switch_state: Mapped[bool | None] = mapped_column(Boolean)
    voltage_v: Mapped[float | None] = mapped_column(Float)
    current_a: Mapped[float | None] = mapped_column(Float)
    power_w: Mapped[float | None] = mapped_column(Float)
    accumulated_energy: Mapped[float | None] = mapped_column(Float)
    raw_datapoints: Mapped[dict[str, Any] | None] = mapped_column(JSON_DATA)


class ControlEventRecord(Base):
    __tablename__ = "control_events"
    __table_args__ = (
        Index("ix_control_events_device_timestamp", "device_id", "timestamp"),
        Index("ix_control_events_user_requested_at", "user_id", "requested_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL")
    )
    command: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    requested_by: Mapped[str | None] = mapped_column(String(255))
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON_DATA)
    request_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    role: Mapped[str | None] = mapped_column(String(20))
    area_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("areas.id", ondelete="SET NULL"))
    action: Mapped[str | None] = mapped_column(String(120))
    previous_value: Mapped[Any | None] = mapped_column(JSON_DATA)
    requested_value: Mapped[Any | None] = mapped_column(JSON_DATA)
    reason: Mapped[str | None] = mapped_column(Text)
    client_ip: Mapped[str | None] = mapped_column(String(64))
    requested_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    hardware_acknowledgement: Mapped[bool | None] = mapped_column(Boolean)
    verified_value: Mapped[Any | None] = mapped_column(JSON_DATA)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    error_information: Mapped[str | None] = mapped_column(Text)


class SystemEventRecord(Base):
    __tablename__ = "system_events"
    __table_args__ = (
        Index("ix_system_events_timestamp", "timestamp"),
        Index("ix_system_events_device_timestamp", "device_id", "timestamp"),
        Index("ix_system_events_severity_timestamp", "severity", "timestamp"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL")
    )
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    severity: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON_DATA)


class AlertRecord(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_active_timestamp", "active", "timestamp"),
        Index("ix_alerts_device_timestamp", "device_id", "timestamp"),
        Index("ix_alerts_category_active", "category", "active"),
        Index("ix_alerts_dedup_key", "dedup_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("devices.id", ondelete="SET NULL")
    )
    severity: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    alert_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSON_DATA)
    first_seen: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_seen: Mapped[datetime | None] = mapped_column(UTCDateTime())
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    acknowledged_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    area_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("areas.id", ondelete="SET NULL"))
    category: Mapped[str | None] = mapped_column(String(120))
    dedup_key: Mapped[str | None] = mapped_column(String(512))


class BackupRunRecord(Base):
    __tablename__ = "backup_runs"
    __table_args__ = (
        Index("ix_backup_runs_started_at", "started_at"),
        Index("ix_backup_runs_status_started_at", "status", "started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    output_size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    filename: Mapped[str | None] = mapped_column(String(255))
    destination: Mapped[str] = mapped_column(String(30), nullable=False, default="primary")
    error_information: Mapped[str | None] = mapped_column(Text)


class LoadSheddingStateRecord(Base):
    """Persistent ownership of relay changes made by battery automation."""

    __tablename__ = "load_shedding_states"
    __table_args__ = (
        UniqueConstraint("policy_name", name="uq_load_shedding_states_policy_name"),
        Index("ix_load_shedding_states_device", "device_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    policy_name: Mapped[str] = mapped_column(String(80), nullable=False)
    device_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("devices.id", ondelete="CASCADE"), nullable=False
    )
    automatically_shed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    last_transition: Mapped[str | None] = mapped_column(String(20))
    last_transition_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_error: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, onupdate=utc_now, server_default=func.now()
    )


# Concise persistence names for repository and migration consumers. Domain models
# retain their existing names in their own modules.
Area = AreaRecord
Device = DeviceRecord
InverterReading = InverterReadingRecord
BatteryReading = BatteryReadingRecord
SolarReading = SolarReadingRecord
GridReading = GridReadingRecord
BreakerReading = BreakerReadingRecord
ControlEvent = ControlEventRecord
SystemEvent = SystemEventRecord
Alert = AlertRecord
User = UserRecord
BackupRun = BackupRunRecord
LoadSheddingState = LoadSheddingStateRecord
InstallationState = InstallationStateRecord

__all__ = [
    "Alert", "AlertRecord", "Area", "AreaRecord", "BackupRun", "BackupRunRecord", "BatteryReading", "BatteryReadingRecord",
    "BreakerReading", "BreakerReadingRecord", "ControlEvent", "ControlEventRecord", "Device",
    "DeviceRecord", "GridReading", "GridReadingRecord", "InverterReading",
    "InverterReadingRecord", "SolarReading", "SolarReadingRecord", "SystemEvent",
    "SystemEventRecord", "User", "UserRecord", "LoadSheddingState", "LoadSheddingStateRecord",
    "InstallationState", "InstallationStateRecord",
]
