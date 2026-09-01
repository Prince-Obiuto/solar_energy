"""Add safe breaker-control audit fields and idempotency key."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260901_03"
down_revision: str | None = "20260901_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
JSON_DATA = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    with op.batch_alter_table("control_events") as batch:
        batch.add_column(sa.Column("request_id", sa.String(64)))
        batch.add_column(sa.Column("user_id", sa.Uuid()))
        batch.add_column(sa.Column("role", sa.String(20)))
        batch.add_column(sa.Column("area_id", sa.Uuid()))
        batch.add_column(sa.Column("action", sa.String(120)))
        batch.add_column(sa.Column("previous_value", JSON_DATA))
        batch.add_column(sa.Column("requested_value", JSON_DATA))
        batch.add_column(sa.Column("reason", sa.Text()))
        batch.add_column(sa.Column("client_ip", sa.String(64)))
        batch.add_column(sa.Column("requested_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("hardware_acknowledgement", sa.Boolean()))
        batch.add_column(sa.Column("verified_value", JSON_DATA))
        batch.add_column(sa.Column("completed_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("error_information", sa.Text()))
        batch.create_foreign_key("fk_control_events_user_id", "users", ["user_id"], ["id"], ondelete="SET NULL")
        batch.create_foreign_key("fk_control_events_area_id", "areas", ["area_id"], ["id"], ondelete="SET NULL")
        batch.create_unique_constraint("uq_control_events_request_id", ["request_id"])
        batch.create_index("ix_control_events_user_requested_at", ["user_id", "requested_at"])


def downgrade() -> None:
    with op.batch_alter_table("control_events") as batch:
        batch.drop_index("ix_control_events_user_requested_at")
        batch.drop_constraint("uq_control_events_request_id", type_="unique")
        batch.drop_constraint("fk_control_events_area_id", type_="foreignkey")
        batch.drop_constraint("fk_control_events_user_id", type_="foreignkey")
        for column in (
            "error_information", "completed_at", "verified_value", "hardware_acknowledgement",
            "requested_at", "client_ip", "reason", "requested_value", "previous_value",
            "action", "area_id", "role", "user_id", "request_id",
        ):
            batch.drop_column(column)
