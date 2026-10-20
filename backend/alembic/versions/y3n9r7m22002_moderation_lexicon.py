"""Add moderation lexicon policy snapshots (shadow-only rollout).

Revision ID: y3n9r7m22002
Revises: x2m8q6l11001
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "y3n9r7m22002"
down_revision = "x2m8q6l11001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "moderation_lexicon_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("active_revision", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("mode", sa.String(16), nullable=False, server_default="off"),
        sa.Column("updated_by_account_uid", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["updated_by_account_uid"], ["accounts.uid"], ondelete="SET NULL"),
        sa.CheckConstraint("id = 1", name="ck_lexicon_singleton"),
        sa.CheckConstraint("mode IN ('off','shadow')", name="ck_lexicon_mode"),
    )
    op.create_table(
        "moderation_lexicon_revisions",
        sa.Column("revision", sa.Integer(), primary_key=True),
        sa.Column("rules", sa.JSON(), nullable=False),
        sa.Column("created_by_account_uid", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["created_by_account_uid"], ["accounts.uid"], ondelete="SET NULL"),
    )
    op.create_table(
        "moderation_lexicon_audit",
        sa.Column("uid", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("actor_account_uid", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(24), nullable=False),
        sa.Column("previous_revision", sa.Integer(), nullable=False),
        sa.Column("next_revision", sa.Integer(), nullable=False),
        sa.Column("previous_mode", sa.String(16), nullable=False),
        sa.Column("next_mode", sa.String(16), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["actor_account_uid"], ["accounts.uid"], ondelete="SET NULL"),
    )
    op.execute("INSERT INTO moderation_lexicon_state (id, active_revision, mode) VALUES (1, 0, 'off')")
    op.execute("""
        INSERT INTO platform_permissions (name, description)
        VALUES ('moderation.policy.manage', 'Manage audited moderation lexicon revisions and simulate rules')
        ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description
    """)
    # Only admin has policy editing powers; ordinary platform moderators retain only their existing powers.
    op.execute("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT id, (SELECT id FROM platform_permissions WHERE name = 'moderation.policy.manage')
        FROM platform_roles WHERE name = 'admin'
        ON CONFLICT DO NOTHING
    """)


def downgrade() -> None:
    op.execute("""DELETE FROM role_permissions WHERE permission_id IN
                  (SELECT id FROM platform_permissions WHERE name='moderation.policy.manage')""")
    op.execute("DELETE FROM platform_permissions WHERE name='moderation.policy.manage'")
    op.drop_table("moderation_lexicon_audit")
    op.drop_table("moderation_lexicon_revisions")
    op.drop_table("moderation_lexicon_state")
