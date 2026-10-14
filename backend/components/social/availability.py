from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from components.identity.model import Persona
from components.social.availability_model import PersonaSocialAvailability


LIVE_INTENTS = {"open", "meet", "games"}


class SocialAvailabilityRequest(BaseModel):
    intent: str
    duration_minutes: int = Field(ge=15, le=480)
    note: str | None = Field(default=None, max_length=120)


def availability_projection(value: PersonaSocialAvailability | None, *, now: datetime | None = None) -> dict | None:
    now = now or datetime.utcnow()
    if not value or value.expires_at <= now:
        return None
    return {
        "intent": value.intent,
        "note": value.note,
        "expires_at": value.expires_at.isoformat(),
        "updated_at": value.updated_at.isoformat() if value.updated_at else None,
    }


async def _primary_persona(db: AsyncSession, account_uid: UUID | str) -> Persona:
    result = await db.execute(
        select(Persona)
        .where(Persona.account_uid == UUID(str(account_uid)), Persona.is_primary.is_(True))
        .limit(1)
    )
    persona = result.scalar_one_or_none()
    if not persona:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_type": "persona_not_found"},
        )
    return persona


async def get_social_availability(db: AsyncSession, account_uid: UUID | str) -> dict | None:
    persona = await _primary_persona(db, account_uid)
    value = await db.get(PersonaSocialAvailability, persona.uid)
    projection = availability_projection(value)
    if value and projection is None:
        await db.delete(value)
        await db.commit()
    return projection


async def set_social_availability(
    db: AsyncSession,
    account_uid: UUID | str,
    payload: SocialAvailabilityRequest,
) -> dict:
    if payload.intent not in LIVE_INTENTS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error_type": "invalid_live_social_intent"},
        )

    persona = await _primary_persona(db, account_uid)
    now = datetime.utcnow()
    value = await db.get(PersonaSocialAvailability, persona.uid)
    if value is None:
        value = PersonaSocialAvailability(persona_uid=persona.uid)
        db.add(value)

    value.intent = payload.intent
    value.note = (payload.note or "").strip()[:120] or None
    value.expires_at = now + timedelta(minutes=payload.duration_minutes)
    value.updated_at = now
    await db.commit()
    await db.refresh(value)
    return availability_projection(value, now=now) or {}


async def clear_social_availability(db: AsyncSession, account_uid: UUID | str) -> None:
    persona = await _primary_persona(db, account_uid)
    await db.execute(
        delete(PersonaSocialAvailability).where(PersonaSocialAvailability.persona_uid == persona.uid)
    )
    await db.commit()
