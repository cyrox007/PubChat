from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database import Database


class Account(Database.Base):
    __tablename__ = "accounts"

    uid = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    legacy_user_uid = Column(UUID(as_uuid=True), ForeignKey("users.uid"), unique=True, nullable=True)
    status = Column(String(32), nullable=False, default="active")
    trust_level = Column(String(32), nullable=False, default="new")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

    personas = relationship("Persona", back_populates="account", cascade="all, delete-orphan")
    credentials = relationship("Credential", back_populates="account", cascade="all, delete-orphan")
    sessions = relationship("IdentitySession", back_populates="account", cascade="all, delete-orphan")


class Persona(Database.Base):
    __tablename__ = "personas"

    uid = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    account_uid = Column(UUID(as_uuid=True), ForeignKey("accounts.uid", ondelete="CASCADE"), nullable=False, index=True)
    handle = Column(String(32), nullable=False)
    display_name = Column(String(80), nullable=False)
    avatar = Column(String(255), nullable=True)
    bio = Column(String(500), nullable=True)
    city = Column(String(100), nullable=True)
    country = Column(String(100), nullable=True)
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String(50), nullable=True)
    social_intent = Column(String(32), nullable=False, default="open")
    is_primary = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    account = relationship("Account", back_populates="personas")
    privacy = relationship("PrivacySettings", back_populates="persona", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("handle", name="personas_handle_key"),
        Index("ix_personas_handle", "handle", unique=True),
        Index("ix_personas_account_primary", "account_uid", "is_primary"),
    )


class Credential(Database.Base):
    __tablename__ = "credentials"

    uid = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    account_uid = Column(UUID(as_uuid=True), ForeignKey("accounts.uid", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String(24), nullable=False)
    value_normalized = Column(String(255), nullable=True)
    secret_hash = Column(String(255), nullable=True)
    is_primary = Column(Boolean, nullable=False, default=False)
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    account = relationship("Account", back_populates="credentials")

    __table_args__ = (
        UniqueConstraint("kind", "value_normalized", name="uq_credentials_kind_value"),
        Index("ix_credentials_account_kind", "account_uid", "kind"),
    )


class IdentitySession(Database.Base):
    __tablename__ = "identity_sessions"

    uid = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    account_uid = Column(UUID(as_uuid=True), ForeignKey("accounts.uid", ondelete="CASCADE"), nullable=False, index=True)
    device_uid = Column(UUID(as_uuid=True), nullable=False, default=uuid4)
    refresh_token_hash = Column(String(64), nullable=False)
    device_label = Column(String(120), nullable=True)
    user_agent = Column(Text, nullable=True)
    ip_address = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    last_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)

    account = relationship("Account", back_populates="sessions")

    __table_args__ = (
        UniqueConstraint("refresh_token_hash", name="identity_sessions_refresh_token_hash_key"),
        Index("ix_identity_sessions_refresh_token_hash", "refresh_token_hash", unique=True),
        Index("ix_identity_sessions_account_device", "account_uid", "device_uid"),
    )


class PrivacySettings(Database.Base):
    __tablename__ = "privacy_settings"

    persona_uid = Column(UUID(as_uuid=True), ForeignKey("personas.uid", ondelete="CASCADE"), primary_key=True)
    profile_visibility = Column(String(24), nullable=False, default="public")
    dm_policy = Column(String(32), nullable=False, default="shared_spaces")
    show_last_seen = Column(Boolean, nullable=False, default=True)
    show_age = Column(Boolean, nullable=False, default=False)
    show_location = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    persona = relationship("Persona", back_populates="privacy")


class PlatformRole(Database.Base):
    __tablename__ = "platform_roles"

    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=False, unique=True)
    description = Column(String(255), nullable=True)
    authority_level = Column(Integer, nullable=False, default=0)


class PlatformPermission(Database.Base):
    __tablename__ = "platform_permissions"

    id = Column(Integer, primary_key=True)
    name = Column(String(96), nullable=False, unique=True)
    description = Column(String(255), nullable=True)


class AccountRole(Database.Base):
    __tablename__ = "account_roles"

    account_uid = Column(UUID(as_uuid=True), ForeignKey("accounts.uid", ondelete="CASCADE"), primary_key=True)
    role_id = Column(Integer, ForeignKey("platform_roles.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class RolePermission(Database.Base):
    __tablename__ = "role_permissions"

    role_id = Column(Integer, ForeignKey("platform_roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id = Column(Integer, ForeignKey("platform_permissions.id", ondelete="CASCADE"), primary_key=True)


class AccountRelationship(Database.Base):
    __tablename__ = "account_relationships"

    id = Column(Integer, primary_key=True)
    from_account_uid = Column(UUID(as_uuid=True), ForeignKey("accounts.uid", ondelete="CASCADE"), nullable=False)
    to_account_uid = Column(UUID(as_uuid=True), ForeignKey("accounts.uid", ondelete="CASCADE"), nullable=False)
    relation_type = Column(String(24), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("from_account_uid", "to_account_uid", "relation_type", name="uq_account_relationship"),
        Index("ix_account_relationship_from", "from_account_uid", "relation_type"),
        Index("ix_account_relationship_to", "to_account_uid", "relation_type"),
    )
