from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from database import Database


class EncryptedPrivateAttachment(Database.Base):
    """Opaque ciphertext blob metadata for an E2EE direct-message attachment.

    Original filename, MIME type, content key and AES-GCM nonce deliberately do not
    belong to the server schema. Those values travel only inside the per-device E2EE
    message payload.
    """

    __tablename__ = "encrypted_private_attachments"

    uid = Column(UUID(as_uuid=True), primary_key=True)
    uploader_account_uid = Column(
        UUID(as_uuid=True),
        ForeignKey("accounts.uid", ondelete="CASCADE"),
        nullable=False,
    )
    message_uid = Column(
        UUID(as_uuid=True),
        ForeignKey("private_messages.uid", ondelete="CASCADE"),
        nullable=True,
        unique=True,
    )
    storage_name = Column(String(96), nullable=False, unique=True)
    ciphertext_size = Column(Integer, nullable=False)
    ciphertext_sha256 = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    attached_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index(
            "ix_encrypted_private_attachment_uploader_pending",
            "uploader_account_uid",
            "attached_at",
        ),
        Index(
            "ix_encrypted_private_attachment_message",
            "message_uid",
        ),
    )
