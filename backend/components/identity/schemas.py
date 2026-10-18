from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator


SocialIntent = Literal["open", "meet", "games", "friends", "quiet"]
DMPolicy = Literal["everyone", "shared_spaces", "mutual", "nobody"]
ProfileVisibility = Literal["public", "shared_spaces", "private"]


class RegisterRequest(BaseModel):
    handle: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_.]+$")
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=128)
    email: Optional[EmailStr] = None
    bio: Optional[str] = Field(default=None, max_length=500)
    social_intent: SocialIntent = "open"

    @field_validator("handle")
    @classmethod
    def normalize_handle(cls, value: str) -> str:
        return value.strip()

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if value else value


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class ProfilesBatchRequest(BaseModel):
    account_uids: list[UUID] = Field(min_length=1, max_length=100)


class PersonaCreateRequest(BaseModel):
    handle: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_.]+$")
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    bio: Optional[str] = Field(default=None, max_length=500)
    social_intent: SocialIntent = "open"

    @field_validator("handle")
    @classmethod
    def normalize_handle(cls, value: str) -> str:
        return value.strip()

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if value else value


class PersonaUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    avatar: Optional[str] = Field(default=None, max_length=255)
    bio: Optional[str] = Field(default=None, max_length=500)
    city: Optional[str] = Field(default=None, max_length=100)
    country: Optional[str] = Field(default=None, max_length=100)
    social_intent: Optional[SocialIntent] = None


class PrivacyUpdateRequest(BaseModel):
    profile_visibility: Optional[ProfileVisibility] = None
    dm_policy: Optional[DMPolicy] = None
    show_last_seen: Optional[bool] = None
    show_age: Optional[bool] = None
    show_location: Optional[bool] = None
