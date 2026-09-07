"""Add encrypted persistent runtime configuration.

Revision ID: 20260907_09
Revises: 20260907_08
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260907_09"
down_revision: str | None = "20260907_08"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "runtime_configuration",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("namespace", sa.String(50), nullable=False),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("is_secret", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "namespace", "key", name="uq_runtime_configuration_namespace_key"
        ),
    )
    op.create_index(
        "ix_runtime_configuration_namespace",
        "runtime_configuration",
        ["namespace"],
    )


def downgrade() -> None:
    op.drop_table("runtime_configuration")
