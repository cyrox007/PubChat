from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from database import Database


class PrivateMessageEnvelope(Database.Base):
    """Opaque per-device ciphertext for one direct message.

    PubChat deliberately stores no message plaintext in this table. Routing metadata
    remains visible to the service because the server still has to deliver envelopes
    to the correct Account/device and enforce abuse/privacy policy.
    """

    __tablename__ = "private_message_envelopes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_uid = Column(
        UUID(as_uuid=True),
        ForeignKey("private_messages.uid", ondelete="CASCADE"),
        nullable=False,
    )
    recipient_account_uid = Column(UUID(as_uuid=True), ForeignKey("accounts.uid", ondelete="CASCADE"), nullable=False)
    recipient_device_uid = Column(
        UUID(as_uuid=True),
        ForeignKey("device_cryptographic_identities.uid", ondelete="CASCADE"),
        nullable=False,
    )
    sender_device_uid = Column(
        UUID(as_uuid=True),
        ForeignKey("device_cryptographic_identities.uid", ondelete="CASCADE"),
        nullable=False,
    )
    session_id = Column(UUID(as_uuid=True), nullable=False)
    counter = Column(Integer, nullable=False)
    nonce = Column(String(32), nullable=False)
    ciphertext = Column(Text, nullable=False)
    initial_header = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "message_uid",
            "recipient_device_uid",
            name="uq_private_message_envelope_message_device",
        ),
        UniqueConstraint(
            "recipient_device_uid",
            "session_id",
            "counter",
            name="uq_private_message_envelope_session_counter",
        ),
        Index(
            "ix_private_message_envelope_recipient_message",
            "recipient_account_uid",
            "message_uid",
        ),
    )
