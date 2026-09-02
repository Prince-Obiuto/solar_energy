"""Add persistent battery load-shedding ownership state."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260902_06"
down_revision: str | None = "20260901_05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "load_shedding_states",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("policy_name", sa.String(80), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=False),
        sa.Column("automatically_shed", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("last_transition", sa.String(20)),
        sa.Column("last_transition_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.Text()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("policy_name", name="uq_load_shedding_states_policy_name"),
    )
    op.create_index("ix_load_shedding_states_device", "load_shedding_states", ["device_id"])


def downgrade() -> None:
    op.drop_table("load_shedding_states")
