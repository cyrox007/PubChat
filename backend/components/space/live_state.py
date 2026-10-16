from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from components.message.model import Message
from components.realtime import realtime_service
from components.space.service import list_spaces
from utils.logger import setup_logger

logger = setup_logger(__name__)

LIVE_MESSAGE_WINDOW_MINUTES = 10
MAX_LIVE_SPACES = 50


async def _presence_counts(room_uids: list[UUID]) -> tuple[dict[UUID, int], bool]:
    if not room_uids:
        return {}, True

    redis = realtime_service.redis
    if redis is None:
        try:
            users = await asyncio.gather(*(realtime_service.room_users(uid) for uid in room_uids))
            return {
                room_uid: len(set(room_users))
                for room_uid, room_users in zip(room_uids, users, strict=True)
            }, True
        except Exception:
            logger.exception("Failed to resolve fallback Space presence for discovery")
            return {}, False

    now = time.time()
    try:
        pipe = redis.pipeline(transaction=False)
        for room_uid in room_uids:
            key = realtime_service._presence_room_key(room_uid)
            pipe.zremrangebyscore(key, "-inf", now)
            pipe.zrangebyscore(key, now, "+inf")
        raw_results = await pipe.execute()
    except Exception:
        logger.exception("Failed to resolve batched Space presence for discovery")
        return {}, False

    counts: dict[UUID, int] = {}
    for index, room_uid in enumerate(room_uids):
        members = raw_results[index * 2 + 1] or []
        user_uids = {
            str(member).split("|", 1)[1]
            for member in members
            if "|" in str(member)
        }
        counts[room_uid] = len(user_uids)
    return counts, True


async def _conversation_state(
    db: AsyncSession,
    room_uids: list[UUID],
    now: datetime,
) -> dict[UUID, dict]:
    if not room_uids:
        return {}

    since = now - timedelta(minutes=LIVE_MESSAGE_WINDOW_MINUTES)
    result = await db.execute(
        select(
            Message.room_uid,
            func.count(Message.uid),
            func.count(func.distinct(Message.author_uid)),
            func.max(Message.created_at),
        )
        .where(
            Message.room_uid.in_(room_uids),
            Message.created_at >= since,
            Message.author_uid.is_not(None),
        )
        .group_by(Message.room_uid)
    )
    return {
        room_uid: {
            "active": int(message_count or 0) > 0,
            "message_count": int(message_count or 0),
            "contributor_count": int(contributor_count or 0),
            "latest_at": latest_at.isoformat() if latest_at else None,
            "window_minutes": LIVE_MESSAGE_WINDOW_MINUTES,
        }
        for room_uid, message_count, contributor_count, latest_at in result.all()
    }


async def get_spaces_live_state(
    db: AsyncSession,
    *,
    viewer_uid: UUID | str,
    space_uids: list[UUID],
) -> dict:
    unique_uids = list(dict.fromkeys(space_uids))[:MAX_LIVE_SPACES]
    if not unique_uids:
        return {"spaces": [], "presence_available": True}

    visible_spaces = await list_spaces(
        db,
        viewer_uid,
        candidate_uids=unique_uids,
        limit=len(unique_uids),
        offset=0,
    )
    visible_uids = [UUID(str(space["uid"])) for space in visible_spaces]
    now = datetime.utcnow()

    presence_task = asyncio.create_task(_presence_counts(visible_uids))
    conversation_task = asyncio.create_task(_conversation_state(db, visible_uids, now))
    (presence_counts, presence_available), conversations = await asyncio.gather(
        presence_task,
        conversation_task,
    )

    states = []
    for room_uid in visible_uids:
        conversation = conversations.get(
            room_uid,
            {
                "active": False,
                "message_count": 0,
                "contributor_count": 0,
                "latest_at": None,
                "window_minutes": LIVE_MESSAGE_WINDOW_MINUTES,
            },
        )
        present_count = presence_counts.get(room_uid) if presence_available else None
        states.append(
            {
                "space_uid": str(room_uid),
                "present_count": present_count,
                "has_people_now": bool(present_count) if present_count is not None else None,
                "conversation": conversation,
                "live": bool((present_count or 0) > 0 or conversation["active"]),
            }
        )

    return {
        "spaces": states,
        "presence_available": presence_available,
        "generated_at": now.isoformat(),
    }
