"""Add alert lifecycle, ownership, category, and deduplication fields."""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260901_04"
down_revision: str | None = "20260901_03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("alerts") as batch:
        batch.add_column(sa.Column("first_seen", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("last_seen", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("resolved_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("acknowledged_by", sa.Uuid()))
        batch.add_column(sa.Column("area_id", sa.Uuid()))
        batch.add_column(sa.Column("category", sa.String(120)))
        batch.add_column(sa.Column("dedup_key", sa.String(512)))
        batch.create_foreign_key("fk_alerts_acknowledged_by", "users", ["acknowledged_by"], ["id"], ondelete="SET NULL")
        batch.create_foreign_key("fk_alerts_area_id", "areas", ["area_id"], ["id"], ondelete="SET NULL")
        batch.create_index("ix_alerts_category_active", ["category", "active"])
        batch.create_index("ix_alerts_dedup_key", ["dedup_key"])


def downgrade() -> None:
    with op.batch_alter_table("alerts") as batch:
        batch.drop_index("ix_alerts_dedup_key")
        batch.drop_index("ix_alerts_category_active")
        batch.drop_constraint("fk_alerts_area_id", type_="foreignkey")
        batch.drop_constraint("fk_alerts_acknowledged_by", type_="foreignkey")
        for column in ("dedup_key", "category", "area_id", "acknowledged_by", "resolved_at", "last_seen", "first_seen"):
            batch.drop_column(column)
