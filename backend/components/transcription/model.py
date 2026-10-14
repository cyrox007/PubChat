from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from database import Database


class MediaTranscriptionJob(Database.Base):
    """Durable speech-to-text job for room or Messenger media.

    Message tables intentionally remain the source of truth for the public result:
    the ready transcript is copied into media_metadata. This table only owns queue,
    retry and provider state.
    """

    __tablename__ = "media_transcription_jobs"

    uid = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    surface = Column(String(16), nullable=False)  # room | messenger
    message_uid = Column(UUID(as_uuid=True), nullable=False)
    media_url = Column(Text, nullable=False)
    status = Column(String(16), nullable=False, default="pending")
    language = Column(String(16), nullable=True)
    text = Column(Text, nullable=True)
    segments = Column(JSON, nullable=False, default=list)
    provider_key = Column(String(32), nullable=True)
    model_name = Column(String(128), nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    available_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_code = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("surface", "message_uid", name="uq_media_transcription_surface_message"),
        Index("ix_media_transcription_queue", "status", "available_at", "created_at"),
    )
