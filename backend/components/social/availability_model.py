from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database import Database


class PersonaSocialAvailability(Database.Base):
    __tablename__ = "persona_social_availability"

    persona_uid = Column(
        UUID(as_uuid=True),
        ForeignKey("personas.uid", ondelete="CASCADE"),
        primary_key=True,
    )
    intent = Column(String(32), nullable=False)
    note = Column(String(120), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    persona = relationship("Persona")

    __table_args__ = (
        Index("ix_persona_social_availability_expires", "expires_at"),
        Index("ix_persona_social_availability_intent_expires", "intent", "expires_at"),
    )
