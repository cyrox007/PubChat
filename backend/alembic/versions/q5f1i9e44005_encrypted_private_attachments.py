"""add encrypted private attachments

Revision ID: q5f1i9e44005
Revises: p4e0h8d33004
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "q5f1i9e44005"
down_revision: Union[str, None] = "p4e0h8d33004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "encrypted_private_attachments",
        sa.Column("uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploader_account_uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_uid", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("storage_name", sa.String(length=96), nullable=False),
        sa.Column("ciphertext_size", sa.Integer(), nullable=False),
        sa.Column("ciphertext_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("attached_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["message_uid"], ["private_messages.uid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploader_account_uid"], ["accounts.uid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("uid"),
        sa.UniqueConstraint("message_uid"),
        sa.UniqueConstraint("storage_name"),
    )
    op.create_index(
        "ix_encrypted_private_attachment_uploader_pending",
        "encrypted_private_attachments",
        ["uploader_account_uid", "attached_at"],
        unique=False,
    )
    op.create_index(
        "ix_encrypted_private_attachment_message",
        "encrypted_private_attachments",
        ["message_uid"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_encrypted_private_attachment_message", table_name="encrypted_private_attachments")
    op.drop_index("ix_encrypted_private_attachment_uploader_pending", table_name="encrypted_private_attachments")
    op.drop_table("encrypted_private_attachments")
