from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class EncryptedEnvelopeInput(BaseModel):
    recipient_device_uid: UUID
    session_id: UUID
    counter: int = Field(ge=0, le=2_147_483_647)
    nonce: str = Field(min_length=1, max_length=32)
    ciphertext: str = Field(min_length=1, max_length=32768)
    initial_header: dict | None = None


class EncryptedMessageSendRequest(BaseModel):
    receiver_uid: UUID
    sender_device_uid: UUID
    front_id: str = Field(min_length=8, max_length=128)
    envelopes: list[EncryptedEnvelopeInput] = Field(min_length=1, max_length=40)


class EnvelopeHistoryRequest(BaseModel):
    message_uids: list[UUID] = Field(min_length=1, max_length=100)
