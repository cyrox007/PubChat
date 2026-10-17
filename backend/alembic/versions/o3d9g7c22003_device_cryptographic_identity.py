"""add device cryptographic identity foundation

Revision ID: o3d9g7c22003
Revises: n2c8f6b11002
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "o3d9g7c22003"
down_revision: Union[str, None] = "n2c8f6b11002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "device_cryptographic_identities",
        sa.Column("uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_label", sa.String(length=120), nullable=True),
        sa.Column("key_version", sa.Integer(), nullable=False),
        sa.Column("identity_signing_key", sa.String(length=64), nullable=False),
        sa.Column("identity_dh_key", sa.String(length=64), nullable=False),
        sa.Column("signed_prekey_id", sa.Integer(), nullable=False),
        sa.Column("signed_prekey_key", sa.String(length=64), nullable=False),
        sa.Column("signed_prekey_signature", sa.String(length=128), nullable=False),
        sa.Column("signed_prekey_created_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["account_uid"], ["accounts.uid"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("uid"),
        sa.UniqueConstraint(
            "account_uid",
            "identity_signing_key",
            name="uq_device_crypto_account_signing_key",
        ),
    )
    op.create_index(
        "ix_device_crypto_account_active",
        "device_cryptographic_identities",
        ["account_uid", "revoked_at"],
        unique=False,
    )

    op.create_table(
        "device_one_time_prekeys",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("prekey_id", sa.Integer(), nullable=False),
        sa.Column("public_key", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("claimed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["device_uid"],
            ["device_cryptographic_identities.uid"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_uid", "prekey_id", name="uq_device_one_time_prekey"),
    )
    op.create_index(
        "ix_device_one_time_prekey_available",
        "device_one_time_prekeys",
        ["device_uid", "claimed_at", "id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_device_one_time_prekey_available",
        table_name="device_one_time_prekeys",
    )
    op.drop_table("device_one_time_prekeys")
    op.drop_index(
        "ix_device_crypto_account_active",
        table_name="device_cryptographic_identities",
    )
    op.drop_table("device_cryptographic_identities")
