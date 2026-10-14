"""add AI-derived account reputation and space privileges

Revision ID: k0a6d4f88018
Revises: m1b7e5a99001
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "k0a6d4f88018"
down_revision: Union[str, None] = "m1b7e5a99001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "account_reputation_assessments",
        sa.Column("uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_key", sa.String(length=32), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("schema_version", sa.String(length=16), nullable=False, server_default="v1"),
        sa.Column("overall_label", sa.String(length=32), nullable=False),
        sa.Column("confidence_percent", sa.Integer(), nullable=False),
        sa.Column("dimensions", sa.JSON(), nullable=False),
        sa.Column("space_creation_eligible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("max_owned_active_spaces", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("behavior_window_days", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("assessed_at", sa.DateTime(), nullable=False),
        sa.Column("valid_until", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["account_uid"], ["accounts.uid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("uid"),
    )
    op.create_index(
        "ix_account_reputation_assessment_account_valid",
        "account_reputation_assessments",
        ["account_uid", "valid_until"],
        unique=False,
    )
    op.create_index(
        "ix_account_reputation_assessment_space_privilege",
        "account_reputation_assessments",
        ["space_creation_eligible", "valid_until"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_account_reputation_assessment_space_privilege",
        table_name="account_reputation_assessments",
    )
    op.drop_index(
        "ix_account_reputation_assessment_account_valid",
        table_name="account_reputation_assessments",
    )
    op.drop_table("account_reputation_assessments")
