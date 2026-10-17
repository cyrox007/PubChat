from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database import Database


class DeviceCryptographicIdentity(Database.Base):
    """Public cryptographic identity for one logical client device.

    Private key material never belongs in PubChat's backend/database. A device UID
    is stable across normal token refresh/login cycles on the same client and is
    generated client-side. Rotating the long-term identity creates a new device
    identity rather than silently replacing this record.
    """

    __tablename__ = "device_cryptographic_identities"

    uid = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    account_uid = Column(
        UUID(as_uuid=True),
        ForeignKey("accounts.uid", ondelete="CASCADE"),
        nullable=False,
    )
    device_label = Column(String(120), nullable=True)
    key_version = Column(Integer, nullable=False, default=1)
    identity_signing_key = Column(String(64), nullable=False)
    identity_dh_key = Column(String(64), nullable=False)
    signed_prekey_id = Column(Integer, nullable=False)
    signed_prekey_key = Column(String(64), nullable=False)
    signed_prekey_signature = Column(String(128), nullable=False)
    signed_prekey_created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    revoked_at = Column(DateTime, nullable=True)

    one_time_prekeys = relationship(
        "DeviceOneTimePreKey",
        back_populates="device",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "account_uid",
            "identity_signing_key",
            name="uq_device_crypto_account_signing_key",
        ),
        Index("ix_device_crypto_account_active", "account_uid", "revoked_at"),
    )


class DeviceOneTimePreKey(Database.Base):
    """One-use X25519 public prekey advertised for asynchronous session setup."""

    __tablename__ = "device_one_time_prekeys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_uid = Column(
        UUID(as_uuid=True),
        ForeignKey("device_cryptographic_identities.uid", ondelete="CASCADE"),
        nullable=False,
    )
    prekey_id = Column(Integer, nullable=False)
    public_key = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    claimed_at = Column(DateTime, nullable=True)

    device = relationship("DeviceCryptographicIdentity", back_populates="one_time_prekeys")

    __table_args__ = (
        UniqueConstraint("device_uid", "prekey_id", name="uq_device_one_time_prekey"),
        Index("ix_device_one_time_prekey_available", "device_uid", "claimed_at", "id"),
    )
