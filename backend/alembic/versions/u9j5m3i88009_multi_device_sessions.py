"""add stable auth device ids for multi-device sessions

Revision ID: u9j5m3i88009
Revises: t8i4l2h77008
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "u9j5m3i88009"
down_revision: Union[str, None] = "t8i4l2h77008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "identity_sessions",
        sa.Column("device_uid", postgresql.UUID(as_uuid=True), nullable=True),
    )
    # Existing sessions predate stable browser/device IDs. Their session UUID is
    # a safe non-secret fallback that preserves one-device-per-existing-session
    # semantics without inventing cross-session grouping.
    op.execute("UPDATE identity_sessions SET device_uid = uid WHERE device_uid IS NULL")
    op.alter_column("identity_sessions", "device_uid", nullable=False)
    op.create_index(
        "ix_identity_sessions_account_device",
        "identity_sessions",
        ["account_uid", "device_uid"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_identity_sessions_account_device", table_name="identity_sessions")
    op.drop_column("identity_sessions", "device_uid")
