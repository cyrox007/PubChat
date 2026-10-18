"""Opt-in private birthday reminders without revealing birth dates.

Revision ID: w1l7p5k00001
Revises: v0k6n4j99010
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "w1l7p5k00001"
down_revision: Union[str, None] = "v0k6n4j99010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "privacy_settings",
        sa.Column("share_birthday_with_friends", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "message_notification_preferences",
        sa.Column("friend_birthday_reminders", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("message_notification_preferences", "friend_birthday_reminders")
    op.drop_column("privacy_settings", "share_birthday_with_friends")
