"""Add installation-state creation timestamp safely.

Revision ID: 20260907_08
Revises: 20260903_07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260907_08"
down_revision: str | None = "20260903_07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    column = sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("installation_state", recreate="always") as batch:
            batch.add_column(column)
    else:
        op.add_column("installation_state", column)


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("installation_state", recreate="always") as batch:
            batch.drop_column("created_at")
    else:
        op.drop_column("installation_state", "created_at")
