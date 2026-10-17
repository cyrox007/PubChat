"""add private conversation encryption preferences

Revision ID: s7h3k1g66007
Revises: r6g2j0f55006
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "s7h3k1g66007"
down_revision: Union[str, None] = "r6g2j0f55006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "private_conversation_encryption",
        sa.Column("account_low_uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_high_uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("set_by_account_uid", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("account_low_uid <> account_high_uid", name="ck_private_conversation_encryption_distinct_accounts"),
        sa.CheckConstraint("mode IN ('plaintext', 'e2ee')", name="ck_private_conversation_encryption_mode"),
        sa.ForeignKeyConstraint(["account_high_uid"], ["accounts.uid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_low_uid"], ["accounts.uid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["set_by_account_uid"], ["accounts.uid"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("account_low_uid", "account_high_uid"),
    )


def downgrade() -> None:
    op.drop_table("private_conversation_encryption")
