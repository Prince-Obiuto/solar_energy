"""Add installation runtime activation state.

Revision ID: 20260912_10
Revises: 20260907_09
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260912_10"
down_revision: str | None = "20260907_09"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pending = sa.Column(
        "runtime_activation_pending",
        sa.Boolean(),
        server_default=sa.false(),
        nullable=False,
    )
    activated_at = sa.Column(
        "runtime_activated_at",
        sa.DateTime(timezone=True),
        nullable=True,
    )
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("installation_state", recreate="always") as batch:
            batch.add_column(pending)
            batch.add_column(activated_at)
    else:
        op.add_column("installation_state", pending)
        op.add_column("installation_state", activated_at)


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("installation_state", recreate="always") as batch:
            batch.drop_column("runtime_activated_at")
            batch.drop_column("runtime_activation_pending")
    else:
        op.drop_column("installation_state", "runtime_activated_at")
        op.drop_column("installation_state", "runtime_activation_pending")
