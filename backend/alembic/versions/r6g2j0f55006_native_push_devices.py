"""add native push device registrations

Revision ID: r6g2j0f55006
Revises: q5f1i9e44005
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "r6g2j0f55006"
down_revision: Union[str, None] = "q5f1i9e44005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "message_notification_preferences",
        sa.Column("native_push_messenger", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "message_notification_preferences",
        sa.Column("native_push_space", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.alter_column("message_notification_preferences", "native_push_messenger", server_default=None)
    op.alter_column("message_notification_preferences", "native_push_space", server_default=None)

    op.create_table(
        "native_push_devices",
        sa.Column("uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("installation_uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("platform", sa.String(length=16), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("device_label", sa.String(length=120), nullable=True),
        sa.Column("app_version", sa.String(length=40), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["account_uid"], ["accounts.uid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("uid"),
        sa.UniqueConstraint("installation_uid", name="uq_native_push_installation"),
        sa.UniqueConstraint("token_hash", name="uq_native_push_token_hash"),
    )
    op.create_index(
        "ix_native_push_account_active",
        "native_push_devices",
        ["account_uid", "revoked_at", "updated_at"],
        unique=False,
    )
    op.create_index(
        "ix_native_push_provider_active",
        "native_push_devices",
        ["provider", "revoked_at", "updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_native_push_provider_active", table_name="native_push_devices")
    op.drop_index("ix_native_push_account_active", table_name="native_push_devices")
    op.drop_table("native_push_devices")
    op.drop_column("message_notification_preferences", "native_push_space")
    op.drop_column("message_notification_preferences", "native_push_messenger")
