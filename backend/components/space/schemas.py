import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator
from components.space.category_schemas import normalize_category_slugs


SpacePurpose = Literal["community", "conversation", "meet_people", "games", "local"]
SpaceVisibility = Literal["public", "unlisted", "private"]
SpaceJoinPolicy = Literal["open", "request", "invite"]


def _normalize_optional_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = re.sub(r"\s+", " ", value).strip()
    return normalized or None


def _normalize_required_name(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value).strip()
    if len(normalized) < 3:
        raise ValueError("Space name must contain at least 3 visible characters")
    return normalized


def _normalize_tag_list(tags: list[str]) -> list[str]:
    normalized: list[str] = []
    seen = set()
    for raw_tag in tags:
        tag = re.sub(r"\s+", " ", str(raw_tag)).strip()
        if not tag:
            continue
        if len(tag) > 40:
            raise ValueError("Each tag must be at most 40 characters")
        key = tag.casefold()
        if key not in seen:
            seen.add(key)
            normalized.append(tag)
    return normalized[:8]


class SpaceCreateRequest(BaseModel):
    name: str = Field(min_length=3, max_length=80)
    description: Optional[str] = Field(default=None, max_length=500)
    purpose: SpacePurpose = "community"
    visibility: SpaceVisibility = "public"
    join_policy: SpaceJoinPolicy = "open"
    language: Optional[str] = Field(default=None, min_length=2, max_length=16)
    member_limit: int = Field(default=250, ge=2, le=5000)
    region: Optional[str] = Field(default=None, max_length=100)
    country: Optional[str] = Field(default=None, max_length=100)
    tags: list[str] = Field(default_factory=list, max_length=8)
    category_slugs: list[str] = Field(default_factory=list, max_length=3)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return _normalize_required_name(value)

    @field_validator("description", "region", "country", "language")
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_text(value)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, tags: list[str]) -> list[str]:
        return _normalize_tag_list(tags)

    @field_validator("category_slugs")
    @classmethod
    def validate_category_slugs(cls, values: list[str]) -> list[str]:
        return normalize_category_slugs(values)

    @model_validator(mode="after")
    def validate_visibility_policy(self):
        if self.visibility == "private" and self.join_policy != "invite":
            raise ValueError("Private spaces must use invite-only join policy")
        return self


class SpaceUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=3, max_length=80)
    description: Optional[str] = Field(default=None, max_length=500)
    purpose: Optional[SpacePurpose] = None
    visibility: Optional[SpaceVisibility] = None
    join_policy: Optional[SpaceJoinPolicy] = None
    language: Optional[str] = Field(default=None, min_length=2, max_length=16)
    member_limit: Optional[int] = Field(default=None, ge=2, le=5000)
    region: Optional[str] = Field(default=None, max_length=100)
    country: Optional[str] = Field(default=None, max_length=100)
    tags: Optional[list[str]] = Field(default=None, max_length=8)
    category_slugs: Optional[list[str]] = Field(default=None, max_length=3)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        return _normalize_required_name(value)

    @field_validator("description", "region", "country", "language")
    @classmethod
    def normalize_optional_text(cls, value: Optional[str]) -> Optional[str]:
        return _normalize_optional_text(value)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, tags: Optional[list[str]]) -> Optional[list[str]]:
        if tags is None:
            return None
        return _normalize_tag_list(tags)

    @field_validator("category_slugs")
    @classmethod
    def validate_category_slugs(cls, values: Optional[list[str]]) -> Optional[list[str]]:
        return normalize_category_slugs(values) if values is not None else None


class SpaceMembershipRoleUpdateRequest(BaseModel):
    role: Literal["member", "moderator"]
