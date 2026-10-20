"""Track native push delivery per target installation.

Revision ID: z4p8r2t33003
Revises: y3n9r7m22002
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "z4p8r2t33003"
down_revision = "y3n9r7m22002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "native_push_delivery_receipts",
        sa.Column("uid", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ledger_uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_uid", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("provider_message_id", sa.String(180), nullable=True),
        sa.Column("failure_class", sa.String(80), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["ledger_uid"], ["external_delivery_ledger.uid"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["device_uid"], ["native_push_devices.uid"], ondelete="CASCADE"),
        sa.UniqueConstraint("ledger_uid", "device_uid", name="uq_native_push_ledger_device"),
        sa.CheckConstraint("status IN ('pending','delivered','terminal')", name="ck_native_push_receipt_status"),
    )
    op.create_index("ix_native_push_receipt_ledger_status", "native_push_delivery_receipts", ["ledger_uid", "status"])


def downgrade() -> None:
    op.drop_index("ix_native_push_receipt_ledger_status", table_name="native_push_delivery_receipts")
    op.drop_table("native_push_delivery_receipts")
