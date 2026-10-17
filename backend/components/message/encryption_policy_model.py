from datetime import datetime

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID

from database import Database


class PrivateConversationEncryption(Database.Base):
    __tablename__ = "private_conversation_encryption"

    account_low_uid = Column(UUID(as_uuid=True), ForeignKey("accounts.uid", ondelete="CASCADE"), primary_key=True)
    account_high_uid = Column(UUID(as_uuid=True), ForeignKey("accounts.uid", ondelete="CASCADE"), primary_key=True)
    mode = Column(String(16), nullable=False)
    set_by_account_uid = Column(UUID(as_uuid=True), ForeignKey("accounts.uid", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint("account_low_uid <> account_high_uid", name="ck_private_conversation_encryption_distinct_accounts"),
        CheckConstraint("mode IN ('plaintext', 'e2ee')", name="ck_private_conversation_encryption_mode"),
    )
