from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID

from database import Database


class AccountReputationAssessment(Database.Base):
    """Durable AI assessment of account-level social reputation.

    Reputation belongs to Account, never Persona. The record stores the model's
    structured conclusion and an explicit privilege decision; it does not use a
    hand-written points formula and cannot be purchased.
    """

    __tablename__ = "account_reputation_assessments"

    uid = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    account_uid = Column(
        UUID(as_uuid=True),
        ForeignKey("accounts.uid", ondelete="CASCADE"),
        nullable=False,
    )
    provider_key = Column(String(32), nullable=False)
    model_name = Column(String(128), nullable=True)
    schema_version = Column(String(16), nullable=False, default="v1")
    overall_label = Column(String(32), nullable=False)
    confidence_percent = Column(Integer, nullable=False)
    dimensions = Column(JSON, nullable=False, default=dict)
    space_creation_eligible = Column(Boolean, nullable=False, default=False)
    max_owned_active_spaces = Column(Integer, nullable=False, default=0)
    rationale = Column(Text, nullable=True)
    behavior_window_days = Column(Integer, nullable=False, default=90)
    assessed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    valid_until = Column(DateTime, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        Index(
            "ix_account_reputation_assessment_account_valid",
            "account_uid",
            "valid_until",
        ),
        Index(
            "ix_account_reputation_assessment_space_privilege",
            "space_creation_eligible",
            "valid_until",
        ),
    )
