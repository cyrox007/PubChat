"""Versioned, administrator-managed Space taxonomy (independent of free tags/purpose)."""
from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from database import Database


class SpaceCategory(Database.Base):
    __tablename__ = "space_categories"

    slug = Column(String(40), primary_key=True)
    name = Column(String(80), nullable=False)
    icon = Column(String(32), nullable=False, default="tag")
    description = Column(String(300), nullable=True)
    locale = Column(String(12), nullable=False, default="ru")
    position = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)
    archived_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_space_categories_active_order", "is_active", "position", "slug"),
    )


class SpaceCategoryAssignment(Database.Base):
    __tablename__ = "space_category_assignments"

    room_uid = Column(UUID(as_uuid=True), ForeignKey("rooms.uid", ondelete="CASCADE"), primary_key=True)
    category_slug = Column(String(40), ForeignKey("space_categories.slug", ondelete="RESTRICT"), primary_key=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_space_category_assignments_slug_room", "category_slug", "room_uid"),
    )


class SpaceCategoryAudit(Database.Base):
    __tablename__ = "space_category_audit"

    uid = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    category_slug = Column(String(40), nullable=False)
    actor_account_uid = Column(UUID(as_uuid=True), ForeignKey("accounts.uid", ondelete="SET NULL"), nullable=True)
    action = Column(String(32), nullable=False)
    change_summary = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_space_category_audit_slug_created", "category_slug", "created_at"),
    )
