"""add encrypted private message envelopes

Revision ID: p4e0h8d33004
Revises: o3d9g7c22003
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "p4e0h8d33004"
down_revision: Union[str, None] = "o3d9g7c22003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "private_message_envelopes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("message_uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_account_uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_device_uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sender_device_uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("counter", sa.Integer(), nullable=False),
        sa.Column("nonce", sa.String(length=32), nullable=False),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("initial_header", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["message_uid"], ["private_messages.uid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipient_account_uid"], ["accounts.uid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipient_device_uid"], ["device_cryptographic_identities.uid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_device_uid"], ["device_cryptographic_identities.uid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_uid", "recipient_device_uid", name="uq_private_message_envelope_message_device"),
        sa.UniqueConstraint("recipient_device_uid", "session_id", "counter", name="uq_private_message_envelope_session_counter"),
    )
    op.create_index(
        "ix_private_message_envelope_recipient_message",
        "private_message_envelopes",
        ["recipient_account_uid", "message_uid"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_private_message_envelope_recipient_message", table_name="private_message_envelopes")
    op.drop_table("private_message_envelopes")
