from datetime import datetime
from uuid import uuid4

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from database import Database


class DeviceDirectoryEvent(Database.Base):
    """Append-only Account device-directory checkpoint journal.

    This is transparency groundwork, not a malicious-server-resistant public log.
    Clients can detect local rollback/same-sequence fork against checkpoints they
    have already observed. External gossip/independent witnessing is separate.
    """

    __tablename__ = "device_directory_events"

    uid = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    account_uid = Column(
        UUID(as_uuid=True),
        ForeignKey("accounts.uid", ondelete="CASCADE"),
        nullable=False,
    )
    sequence = Column(BigInteger, nullable=False)
    event_type = Column(String(24), nullable=False)
    device_uid = Column(UUID(as_uuid=True), nullable=True)
    key_version = Column(String(16), nullable=True)
    fingerprint = Column(String(64), nullable=True)
    identity_signing_key = Column(Text, nullable=True)
    identity_dh_key = Column(Text, nullable=True)
    previous_hash = Column(String(64), nullable=False)
    directory_hash = Column(String(64), nullable=False)
    event_hash = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("account_uid", "sequence", name="uq_device_directory_event_sequence"),
        UniqueConstraint("account_uid", "event_hash", name="uq_device_directory_event_hash"),
        Index("ix_device_directory_events_account_sequence", "account_uid", "sequence"),
    )
