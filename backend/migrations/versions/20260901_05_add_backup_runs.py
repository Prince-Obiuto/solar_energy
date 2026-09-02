"""Add operational PostgreSQL backup run history."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260901_05"
down_revision: str | None = "20260901_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "backup_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("output_size_bytes", sa.BigInteger()),
        sa.Column("filename", sa.String(255)),
        sa.Column("destination", sa.String(30), nullable=False),
        sa.Column("error_information", sa.Text()),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_backup_runs_started_at", "backup_runs", ["started_at"])
    op.create_index("ix_backup_runs_status_started_at", "backup_runs", ["status", "started_at"])


def downgrade() -> None:
    op.drop_table("backup_runs")
