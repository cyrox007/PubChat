from __future__ import annotations

import base64
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


MAX_ONE_TIME_PREKEY_BATCH = 100
MAX_PREKEY_ID = 2_147_483_647


def _decode_b64url(value: str, *, expected_bytes: int, field_name: str) -> str:
    normalized = value.strip().rstrip("=")
    if not normalized:
        raise ValueError(f"{field_name}_required")
    try:
        padding = "=" * ((4 - len(normalized) % 4) % 4)
        raw = base64.urlsafe_b64decode(normalized + padding)
    except Exception as exc:
        raise ValueError(f"invalid_{field_name}") from exc
    if len(raw) != expected_bytes:
        raise ValueError(f"invalid_{field_name}")
    canonical = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    if canonical != normalized:
        raise ValueError(f"invalid_{field_name}")
    return canonical


KeyId = Annotated[int, Field(ge=0, le=MAX_PREKEY_ID)]


class SignedPreKeyInput(BaseModel):
    id: KeyId
    public_key: str
    signature: str

    @field_validator("public_key")
    @classmethod
    def validate_public_key(cls, value: str) -> str:
        return _decode_b64url(value, expected_bytes=32, field_name="signed_prekey")

    @field_validator("signature")
    @classmethod
    def validate_signature(cls, value: str) -> str:
        return _decode_b64url(value, expected_bytes=64, field_name="signed_prekey_signature")


class OneTimePreKeyInput(BaseModel):
    id: KeyId
    public_key: str

    @field_validator("public_key")
    @classmethod
    def validate_public_key(cls, value: str) -> str:
        return _decode_b64url(value, expected_bytes=32, field_name="one_time_prekey")


class DeviceRegistrationRequest(BaseModel):
    device_uid: UUID
    device_label: str | None = Field(default=None, max_length=120)
    key_version: int = Field(default=1, ge=1, le=16)
    identity_signing_key: str
    identity_dh_key: str
    signed_prekey: SignedPreKeyInput
    one_time_prekeys: list[OneTimePreKeyInput] = Field(
        default_factory=list,
        max_length=MAX_ONE_TIME_PREKEY_BATCH,
    )

    @field_validator("identity_signing_key")
    @classmethod
    def validate_identity_signing_key(cls, value: str) -> str:
        return _decode_b64url(value, expected_bytes=32, field_name="identity_signing_key")

    @field_validator("identity_dh_key")
    @classmethod
    def validate_identity_dh_key(cls, value: str) -> str:
        return _decode_b64url(value, expected_bytes=32, field_name="identity_dh_key")

    @field_validator("device_label")
    @classmethod
    def normalize_device_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("one_time_prekeys")
    @classmethod
    def unique_one_time_prekey_ids(cls, value: list[OneTimePreKeyInput]) -> list[OneTimePreKeyInput]:
        ids = [item.id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate_one_time_prekey_id")
        return value


class SignedPreKeyRotationRequest(BaseModel):
    signed_prekey: SignedPreKeyInput


class OneTimePreKeyBatchRequest(BaseModel):
    one_time_prekeys: list[OneTimePreKeyInput] = Field(
        min_length=1,
        max_length=MAX_ONE_TIME_PREKEY_BATCH,
    )

    @field_validator("one_time_prekeys")
    @classmethod
    def unique_one_time_prekey_ids(cls, value: list[OneTimePreKeyInput]) -> list[OneTimePreKeyInput]:
        ids = [item.id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate_one_time_prekey_id")
        return value
