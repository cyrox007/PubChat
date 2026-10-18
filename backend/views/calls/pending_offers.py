"""Short-lived, account-scoped incoming offer recovery for Android wakeups.

Contains SDP only in Redis, NEVER in FCM or audit logs.
"""
from __future__ import annotations

import json
from uuid import UUID

from components.realtime import realtime_service

TTL_SECONDS = 60
PREFIX = "pubchat:calls:pending:v1:"


def _key(account_uid: UUID) -> str:
    return f"{PREFIX}{account_uid}"


async def save_pending_offer(recipient_uid: UUID, payload: dict) -> bool:
    redis = realtime_service.redis
    if redis is None:
        return False
    await redis.set(_key(recipient_uid), json.dumps(payload, separators=(",", ":")), ex=TTL_SECONDS)
    return True


async def get_pending_offer(recipient_uid: UUID) -> dict | None:
    redis = realtime_service.redis
    if redis is None:
        return None
    raw = await redis.get(_key(recipient_uid))
    if not raw:
        return None
    return json.loads(raw)


async def clear_pending_offer(recipient_uid: UUID, call_uid: str) -> None:
    redis = realtime_service.redis
    if redis is None:
        return
    key = _key(recipient_uid)
    # Atomically remove only the matching call; an old hangup must not clear a new offer.
    script = """
    local raw = redis.call('GET', KEYS[1])
    if not raw then return 0 end
    local parsed = cjson.decode(raw)
    if parsed.call_uid ~= ARGV[1] then return 0 end
    return redis.call('DEL', KEYS[1])
    """
    await redis.eval(script, 1, key, call_uid)
