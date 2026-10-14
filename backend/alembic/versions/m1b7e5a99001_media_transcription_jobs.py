"""add messaging media infrastructure

Revision ID: m1b7e5a99001
Revises: k0a6d4f88017
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "m1b7e5a99001"
down_revision: Union[str, None] = "k0a6d4f88017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "media_transcription_jobs",
        sa.Column("uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("surface", sa.String(length=16), nullable=False),
        sa.Column("message_uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("media_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("segments", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("provider_key", sa.String(length=32), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("uid"),
        sa.UniqueConstraint("surface", "message_uid", name="uq_media_transcription_surface_message"),
    )
    op.create_index("ix_media_transcription_queue", "media_transcription_jobs", ["status", "available_at", "created_at"], unique=False)

    op.create_table(
        "message_reactions",
        sa.Column("uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("surface", sa.String(length=16), nullable=False),
        sa.Column("message_uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("emoji", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("uid"),
        sa.UniqueConstraint("surface", "message_uid", "user_uid", "emoji", name="uq_message_reaction_actor_emoji"),
    )
    op.create_index("ix_message_reactions_message", "message_reactions", ["surface", "message_uid", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_message_reactions_message", table_name="message_reactions")
    op.drop_table("message_reactions")
    op.drop_index("ix_media_transcription_queue", table_name="media_transcription_jobs")
    op.drop_table("media_transcription_jobs")
