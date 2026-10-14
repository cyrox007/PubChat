from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from database import Database


class MessageReaction(Database.Base):
    """Account/user reaction attached to a room or Messenger message."""

    __tablename__ = "message_reactions"

    uid = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    surface = Column(String(16), nullable=False)  # room | messenger
    message_uid = Column(UUID(as_uuid=True), nullable=False)
    user_uid = Column(UUID(as_uuid=True), nullable=False)
    emoji = Column(String(32), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("surface", "message_uid", "user_uid", "emoji", name="uq_message_reaction_actor_emoji"),
        Index("ix_message_reactions_message", "surface", "message_uid", "created_at"),
    )
