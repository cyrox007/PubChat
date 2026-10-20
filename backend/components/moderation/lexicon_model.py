"""Versioned, immutable lexicon policy revisions; no user message contents stored here."""
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID

from database import Database


class ModerationLexiconState(Database.Base):
    __tablename__ = "moderation_lexicon_state"
    id = Column(Integer, primary_key=True)
    active_revision = Column(Integer, nullable=False, default=0)
    mode = Column(String(16), nullable=False, default="off")
    updated_by_account_uid = Column(UUID(as_uuid=True), ForeignKey("accounts.uid", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ModerationLexiconRevision(Database.Base):
    __tablename__ = "moderation_lexicon_revisions"
    revision = Column(Integer, primary_key=True)
    rules = Column(JSON, nullable=False)
    created_by_account_uid = Column(UUID(as_uuid=True), ForeignKey("accounts.uid", ondelete="SET NULL"), nullable=True)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ModerationLexiconAudit(Database.Base):
    __tablename__ = "moderation_lexicon_audit"
    uid = Column(Integer, primary_key=True, autoincrement=True)
    actor_account_uid = Column(UUID(as_uuid=True), ForeignKey("accounts.uid", ondelete="SET NULL"), nullable=True)
    action = Column(String(24), nullable=False)
    previous_revision = Column(Integer, nullable=False)
    next_revision = Column(Integer, nullable=False)
    previous_mode = Column(String(16), nullable=False)
    next_mode = Column(String(16), nullable=False)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
