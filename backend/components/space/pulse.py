from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from components.engagement.model import SpaceActivity
from components.engagement.occurrence_model import ActivityOccurrence
from components.identity.model import Persona
from components.message.model import Message
from components.social.availability_model import PersonaSocialAvailability
from components.space.model import SpaceEvent, SpaceHistoryEntry, SpaceMembership
from components.space.service import get_space


CHAT_WINDOW_MINUTES = 30
LIVE_PEOPLE_PREVIEW_LIMIT = 8
HISTORY_PREVIEW_LIMIT = 5


def _conversation_state(message_count: int, contributor_count: int) -> str:
    """Return a human-oriented pulse state, not a reputation/ranking score."""
    if contributor_count >= 4 and message_count >= 8:
        return "lively"
    if contributor_count >= 2 and message_count >= 3:
        return "active"
    if message_count > 0:
        return "warming"
    return "quiet"


async def _conversation_projection(
    db: AsyncSession,
    space_uid: UUID,
    *,
    now: datetime,
) -> dict:
    since = now - timedelta(minutes=CHAT_WINDOW_MINUTES)
    result = await db.execute(
        select(
            func.count(Message.uid),
            func.count(func.distinct(Message.author_uid)),
            func.max(Message.created_at),
        ).where(
            Message.room_uid == space_uid,
            Message.created_at >= since,
        )
    )
    message_count, contributor_count, latest_message_at = result.one()
    message_count = int(message_count or 0)
    contributor_count = int(contributor_count or 0)
    return {
        "state": _conversation_state(message_count, contributor_count),
        "window_minutes": CHAT_WINDOW_MINUTES,
        "message_count": message_count,
        "contributor_count": contributor_count,
        "latest_message_at": latest_message_at.isoformat() if latest_message_at else None,
    }


async def _availability_projection(
    db: AsyncSession,
    space_uid: UUID,
    *,
    now: datetime,
) -> dict:
    base_filters = (
        SpaceMembership.room_uid == space_uid,
        SpaceMembership.status == "active",
        Persona.account_uid == SpaceMembership.account_uid,
        Persona.is_primary.is_(True),
        PersonaSocialAvailability.persona_uid == Persona.uid,
        PersonaSocialAvailability.expires_at > now,
    )

    count_result = await db.execute(
        select(func.count(Persona.uid))
        .select_from(SpaceMembership)
        .join(Persona, Persona.account_uid == SpaceMembership.account_uid)
        .join(
            PersonaSocialAvailability,
            PersonaSocialAvailability.persona_uid == Persona.uid,
        )
        .where(*base_filters)
    )
    count = int(count_result.scalar_one() or 0)

    result = await db.execute(
        select(Persona, PersonaSocialAvailability)
        .select_from(SpaceMembership)
        .join(Persona, Persona.account_uid == SpaceMembership.account_uid)
        .join(
            PersonaSocialAvailability,
            PersonaSocialAvailability.persona_uid == Persona.uid,
        )
        .where(*base_filters)
        .order_by(PersonaSocialAvailability.updated_at.desc())
        .limit(LIVE_PEOPLE_PREVIEW_LIMIT)
    )
    people = []
    for persona, availability in result.all():
        people.append(
            {
                "account_uid": str(persona.account_uid),
                "persona_uid": str(persona.uid),
                "handle": persona.handle,
                "display_name": persona.display_name,
                "avatar": persona.avatar,
                "intent": availability.intent,
                "note": availability.note,
                "expires_at": availability.expires_at.isoformat(),
            }
        )
    return {"count": count, "people": people}


async def _next_moment_projection(
    db: AsyncSession,
    space_uid: UUID,
    *,
    now: datetime,
) -> dict | None:
    occurrence_result = await db.execute(
        select(
            SpaceActivity.uid,
            SpaceActivity.title,
            SpaceActivity.activity_type,
            ActivityOccurrence.starts_at,
        )
        .join(ActivityOccurrence, ActivityOccurrence.activity_uid == SpaceActivity.uid)
        .where(
            SpaceActivity.room_uid == space_uid,
            SpaceActivity.status == "scheduled",
            ActivityOccurrence.status == "scheduled",
            ActivityOccurrence.starts_at >= now,
        )
        .order_by(ActivityOccurrence.starts_at.asc())
        .limit(1)
    )
    occurrence = occurrence_result.first()

    event_result = await db.execute(
        select(SpaceEvent.uid, SpaceEvent.title, SpaceEvent.starts_at)
        .where(
            SpaceEvent.room_uid == space_uid,
            SpaceEvent.status == "scheduled",
            SpaceEvent.starts_at >= now,
        )
        .order_by(SpaceEvent.starts_at.asc())
        .limit(1)
    )
    event = event_result.first()

    candidates: list[dict] = []
    if occurrence:
        activity_uid, title, activity_type, starts_at = occurrence
        candidates.append(
            {
                "kind": "activity",
                "uid": str(activity_uid),
                "title": title,
                "activity_type": activity_type,
                "starts_at": starts_at,
            }
        )
    if event:
        event_uid, title, starts_at = event
        candidates.append(
            {
                "kind": "event",
                "uid": str(event_uid),
                "title": title,
                "starts_at": starts_at,
            }
        )
    if not candidates:
        return None

    item = min(candidates, key=lambda candidate: candidate["starts_at"])
    return {**item, "starts_at": item["starts_at"].isoformat()}


async def _history_projection(db: AsyncSession, space_uid: UUID) -> list[dict]:
    result = await db.execute(
        select(SpaceHistoryEntry)
        .where(SpaceHistoryEntry.room_uid == space_uid)
        .order_by(SpaceHistoryEntry.created_at.desc())
        .limit(HISTORY_PREVIEW_LIMIT)
    )
    return [
        {
            "uid": str(item.uid),
            "event_type": item.event_type,
            "summary": item.summary,
            "created_at": item.created_at.isoformat(),
        }
        for item in result.scalars().all()
    ]


async def get_space_pulse(
    db: AsyncSession,
    space_uid: UUID,
    viewer_uid: UUID | str,
) -> dict:
    """Build a privacy-safe, read-only snapshot of what makes a Space feel alive.

    Canonical Space visibility is checked first. Pulse data is then derived from
    existing communication, membership, availability, activity and history rows;
    no durable pulse score is stored and the projection does not affect trust or
    reputation.
    """
    space = await get_space(db, space_uid, viewer_uid)
    now = datetime.utcnow()

    conversation = await _conversation_projection(db, space_uid, now=now)
    available_now = await _availability_projection(db, space_uid, now=now)
    next_moment = await _next_moment_projection(db, space_uid, now=now)
    recent_history = await _history_projection(db, space_uid)

    return {
        "space_uid": str(space_uid),
        "generated_at": now.isoformat(),
        "member_count": int(space.get("member_count") or 0),
        "conversation": conversation,
        "available_now": available_now,
        "next_moment": next_moment,
        "recent_history": recent_history,
    }
