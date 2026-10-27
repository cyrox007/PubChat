"""Persist client message identity across reconnects and retries.

Revision ID: a5q9s4u44004
Revises: z4p8r2t33003
"""
from alembic import op
import sqlalchemy as sa

revision = "a5q9s4u44004"
down_revision = "z4p8r2t33003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # NULL preserves legacy messages sent without a client correlation id.
    op.add_column("messages", sa.Column("front_id", sa.String(length=128), nullable=True))
    op.add_column("private_messages", sa.Column("front_id", sa.String(length=128), nullable=True))
    op.create_unique_constraint(
        "uq_room_message_client_id", "messages",
        ["room_uid", "author_uid", "front_id"],
    )
    op.create_unique_constraint(
        "uq_private_message_client_id", "private_messages",
        ["sender_uid", "receiver_uid", "front_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_private_message_client_id", "private_messages", type_="unique")
    op.drop_constraint("uq_room_message_client_id", "messages", type_="unique")
    op.drop_column("private_messages", "front_id")
    op.drop_column("messages", "front_id")
