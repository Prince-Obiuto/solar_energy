"""Create device, telemetry, event, and alert persistence tables."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260901_01"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


JSON_DATA = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
READING_ID = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def reading_columns() -> list[sa.Column]:
    return [
        sa.Column("id", READING_ID, autoincrement=True, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    ]


def reading_indexes(table: str) -> None:
    op.create_index(f"ix_{table}_device_timestamp", table, ["device_id", "timestamp"])
    op.create_index(f"ix_{table}_timestamp", table, ["timestamp"])


def upgrade() -> None:
    op.create_table(
        "areas",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "devices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_reference", sa.String(255), nullable=False),
        sa.Column("friendly_name", sa.String(255), nullable=False),
        sa.Column("device_type", sa.String(50), nullable=False),
        sa.Column("area_id", sa.Uuid(), nullable=True),
        sa.Column("manufacturer", sa.String(120), nullable=True),
        sa.Column("model", sa.String(120), nullable=True),
        sa.Column("protocol", sa.String(50), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["area_id"], ["areas.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_reference", name="uq_devices_external_reference"),
    )
    op.create_index("ix_devices_area_type", "devices", ["area_id", "device_type"])
    op.create_index("ix_devices_enabled_type", "devices", ["enabled", "device_type"])

    op.create_table(
        "inverter_readings",
        *reading_columns(),
        sa.Column("status", sa.String(120)),
        sa.Column("rated_power_w", sa.Float()),
        sa.Column("output_voltage", sa.Float()),
        sa.Column("output_frequency", sa.Float()),
        sa.Column("output_power_w", sa.Float()),
        sa.Column("load_percentage", sa.Float()),
    )
    reading_indexes("inverter_readings")
    op.create_table(
        "battery_readings",
        *reading_columns(),
        sa.Column("soc", sa.Float()),
        sa.Column("voltage", sa.Float()),
        sa.Column("charging_current", sa.Float()),
        sa.Column("discharge_current", sa.Float()),
        sa.Column("power_w", sa.Float()),
        sa.Column("status", sa.String(120)),
        sa.Column("charge_stage", sa.String(120)),
        sa.Column("battery_type", sa.String(120)),
    )
    reading_indexes("battery_readings")
    op.create_table(
        "solar_readings",
        *reading_columns(),
        sa.Column("connected", sa.String(120)),
        sa.Column("pv1_voltage", sa.Float()),
        sa.Column("pv1_power_w", sa.Float()),
        sa.Column("pv2_voltage", sa.Float()),
        sa.Column("pv2_power_w", sa.Float()),
        sa.Column("total_power_w", sa.Float()),
        sa.Column("daily_energy_kwh", sa.Float()),
        sa.Column("monthly_energy_kwh", sa.Float()),
        sa.Column("total_energy_kwh", sa.Float()),
    )
    reading_indexes("solar_readings")
    op.create_table(
        "grid_readings",
        *reading_columns(),
        sa.Column("voltage", sa.Float()),
        sa.Column("frequency", sa.Float()),
        sa.Column("power_w", sa.Float()),
    )
    reading_indexes("grid_readings")
    op.create_table(
        "breaker_readings",
        *reading_columns(),
        sa.Column("online", sa.Boolean(), nullable=False),
        sa.Column("switch_state", sa.Boolean()),
        sa.Column("voltage_v", sa.Float()),
        sa.Column("current_a", sa.Float()),
        sa.Column("power_w", sa.Float()),
        sa.Column("accumulated_energy", sa.Float()),
        sa.Column("raw_datapoints", JSON_DATA),
    )
    reading_indexes("breaker_readings")
    op.create_index(
        "ix_breaker_readings_online_timestamp", "breaker_readings", ["online", "timestamp"]
    )

    op.create_table(
        "control_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("device_id", sa.Uuid()),
        sa.Column("command", sa.String(120), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("requested_by", sa.String(255)),
        sa.Column("details", JSON_DATA),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_control_events_device_timestamp", "control_events", ["device_id", "timestamp"])
    op.create_table(
        "system_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("device_id", sa.Uuid()),
        sa.Column("category", sa.String(120), nullable=False),
        sa.Column("severity", sa.String(50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", JSON_DATA),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_system_events_timestamp", "system_events", ["timestamp"])
    op.create_index(
        "ix_system_events_device_timestamp", "system_events", ["device_id", "timestamp"]
    )
    op.create_index(
        "ix_system_events_severity_timestamp", "system_events", ["severity", "timestamp"]
    )
    op.create_table(
        "alerts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("device_id", sa.Uuid()),
        sa.Column("severity", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("metadata", JSON_DATA),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alerts_active_timestamp", "alerts", ["active", "timestamp"])
    op.create_index("ix_alerts_device_timestamp", "alerts", ["device_id", "timestamp"])


def downgrade() -> None:
    op.drop_table("alerts")
    op.drop_table("system_events")
    op.drop_table("control_events")
    op.drop_table("breaker_readings")
    op.drop_table("grid_readings")
    op.drop_table("solar_readings")
    op.drop_table("battery_readings")
    op.drop_table("inverter_readings")
    op.drop_table("devices")
    op.drop_table("areas")
