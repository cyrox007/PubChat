"""add expiring persona social availability

Revision ID: n2c8f6b11002
Revises: k0a6d4f88018
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "n2c8f6b11002"
down_revision: Union[str, None] = "k0a6d4f88018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "persona_social_availability",
        sa.Column("persona_uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("intent", sa.String(length=32), nullable=False),
        sa.Column("note", sa.String(length=120), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["persona_uid"], ["personas.uid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("persona_uid"),
    )
    op.create_index(
        "ix_persona_social_availability_expires",
        "persona_social_availability",
        ["expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_persona_social_availability_intent_expires",
        "persona_social_availability",
        ["intent", "expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_persona_social_availability_intent_expires",
        table_name="persona_social_availability",
    )
    op.drop_index(
        "ix_persona_social_availability_expires",
        table_name="persona_social_availability",
    )
    op.drop_table("persona_social_availability")
