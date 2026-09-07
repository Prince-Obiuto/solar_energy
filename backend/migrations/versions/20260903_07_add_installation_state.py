"""Add singleton first-run installation state."""
from collections.abc import Sequence
from datetime import UTC, datetime
from alembic import op
import sqlalchemy as sa

revision: str = "20260903_07"
down_revision: str | None = "20260902_06"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "installation_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("setup_initialized", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("admin_configured", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("beve_configured", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("tuya_configured", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("devices_verified", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("setup_completed", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("setup_token_hash", sa.String(255)),
        sa.Column("installation_version", sa.String(50)),
        sa.Column("initialized_at", sa.DateTime(timezone=True)),
        sa.Column("admin_configured_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_installation_state_singleton"),
        sa.PrimaryKeyConstraint("id"),
    )
    connection = op.get_bind()
    users = sa.table("users", sa.column("id"))
    has_users = bool(connection.scalar(sa.select(sa.func.count()).select_from(users)))
    now = datetime.now(UTC)
    installation = sa.table(
        "installation_state", sa.column("id"), sa.column("setup_initialized"),
        sa.column("admin_configured"), sa.column("initialized_at"),
        sa.column("admin_configured_at"),
    )
    op.bulk_insert(installation, [{
        "id": 1, "setup_initialized": has_users, "admin_configured": has_users,
        "initialized_at": now if has_users else None,
        "admin_configured_at": now if has_users else None,
    }])


def downgrade() -> None:
    op.drop_table("installation_state")
