from typing import Literal

from pydantic import BaseModel, Field


ReputationLabel = Literal["unknown", "developing", "established", "trusted", "concerning"]
DimensionLabel = Literal["unknown", "low", "medium", "high"]


class ReputationAIAssessment(BaseModel):
    overall_label: ReputationLabel
    confidence_percent: int = Field(ge=0, le=100)
    dimensions: dict[str, DimensionLabel] = Field(default_factory=dict)
    space_creation_eligible: bool = False
    max_owned_active_spaces: int = Field(default=0, ge=0, le=10)
    rationale: str | None = Field(default=None, max_length=2000)
