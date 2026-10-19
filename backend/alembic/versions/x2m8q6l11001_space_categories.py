"""Managed Space category registry without changing legacy purpose or tags.

Revision ID: x2m8q6l11001
Revises: w1l7p5k00001
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "x2m8q6l11001"
down_revision: Union[str, None] = "w1l7p5k00001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INITIAL_CATEGORIES = (
    ("design", "Дизайн", "palette", 10),
    ("technology", "Технологии", "microchip", 20),
    ("games", "Игры", "gamepad", 30),
    ("travel", "Путешествия", "plane", 40),
    ("business", "Бизнес", "briefcase", 50),
    ("art", "Искусство", "paintbrush", 60),
    ("sports", "Спорт", "futbol", 70),
)

def upgrade() -> None:
    op.create_table(
        "space_categories",
        sa.Column("slug", sa.String(40), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("icon", sa.String(32), nullable=False, server_default="tag"),
        sa.Column("description", sa.String(300), nullable=True),
        sa.Column("locale", sa.String(12), nullable=False, server_default="ru"),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_space_categories_active_order", "space_categories", ["is_active", "position", "slug"])
    op.create_table(
        "space_category_assignments",
        sa.Column("room_uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_slug", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["room_uid"], ["rooms.uid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_slug"], ["space_categories.slug"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("room_uid", "category_slug"),
    )
    op.create_index("ix_space_category_assignments_slug_room", "space_category_assignments", ["category_slug", "room_uid"])
    op.create_table(
        "space_category_audit",
        sa.Column("uid", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("category_slug", sa.String(40), nullable=False),
        sa.Column("actor_account_uid", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["actor_account_uid"], ["accounts.uid"], ondelete="SET NULL"),
    )
    op.create_index("ix_space_category_audit_slug_created", "space_category_audit", ["category_slug", "created_at"])
    categories = sa.table(
        "space_categories",
        sa.column("slug", sa.String(40)), sa.column("name", sa.String(80)),
        sa.column("icon", sa.String(32)), sa.column("locale", sa.String(12)),
        sa.column("position", sa.Integer()), sa.column("is_active", sa.Boolean()),
    )
    op.bulk_insert(categories, [
        dict(slug=slug, name=name, icon=icon, locale="ru", position=position, is_active=True)
        for slug, name, icon, position in INITIAL_CATEGORIES
    ])

def downgrade() -> None:
    op.drop_index("ix_space_category_audit_slug_created", table_name="space_category_audit")
    op.drop_table("space_category_audit")
    op.drop_index("ix_space_category_assignments_slug_room", table_name="space_category_assignments")
    op.drop_table("space_category_assignments")
    op.drop_index("ix_space_categories_active_order", table_name="space_categories")
    op.drop_table("space_categories")
