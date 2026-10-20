from __future__ import annotations

import asyncio
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from components.identity.model import AccountRelationship
from components.notification.message_delivery import (
    SURFACE_SPACE,
    message_delivery_policy,
    message_notification_preference_projection,
)
from components.notification.model import MessageNotificationPreference
from components.realtime import realtime_service
from components.space.model import SpaceMembership
from socket_manager import private_manager
from utils.logger import setup_logger

logger = setup_logger(__name__)

_STATUS_BATCH_SIZE = 64
_DELIVERY_BATCH_SIZE = 32


def _batched(values: list[UUID], size: int):
    for index in range(0, len(values), size):
        yield values[index:index + size]


async def _online_members(candidate_uids: list[UUID]) -> list[UUID]:
    online: list[UUID] = []
    for batch in _batched(candidate_uids, _STATUS_BATCH_SIZE):
        results = await asyncio.gather(
            *(realtime_service.is_online(uid) for uid in batch),
            return_exceptions=True,
        )
        for uid, result in zip(batch, results):
            if result is True:
                online.append(uid)
            elif isinstance(result, Exception):
                logger.warning("Could not resolve Space alert presence for account=%s", uid)
    return online


async def notify_online_space_members(
    db: AsyncSession,
    *,
    room_uid: UUID,
    sender_uid: UUID,
    formatted_message: dict,
    exclude_uids: set[UUID] | None = None,
) -> None:
    """Fan out a privacy-safe alert to online members not viewing this room.

    The room message itself continues to use the room channel. This function is
    only the secondary user-level alert surface. Offline members are ignored and
    therefore cannot accidentally become email/push re-engagement recipients.
    Failures here are best-effort and never roll back a persisted chat message.
    """

    try:
        membership_result = await db.execute(
            select(SpaceMembership.account_uid).where(
                SpaceMembership.room_uid == room_uid,
                SpaceMembership.status == "active",
                SpaceMembership.account_uid != sender_uid,
            )
        )
        candidate_uids = list(dict.fromkeys(membership_result.scalars().all()))
        if not candidate_uids:
            return

        blocked_result = await db.execute(
            select(
                AccountRelationship.from_account_uid,
                AccountRelationship.to_account_uid,
            ).where(
                AccountRelationship.relation_type == "block",
                or_(
                    and_(
                        AccountRelationship.from_account_uid == sender_uid,
                        AccountRelationship.to_account_uid.in_(candidate_uids),
                    ),
                    and_(
                        AccountRelationship.to_account_uid == sender_uid,
                        AccountRelationship.from_account_uid.in_(candidate_uids),
                    ),
                ),
            )
        )
        blocked_uids: set[UUID] = set()
        for from_uid, to_uid in blocked_result.all():
            blocked_uids.add(to_uid if from_uid == sender_uid else from_uid)

        candidates = [uid for uid in candidate_uids if uid not in blocked_uids and uid not in (exclude_uids or set())]
        if not candidates:
            return

        # A member already connected to this room sees the canonical room frame;
        # do not duplicate it with a user-level toast/sound on another socket.
        active_in_room = {UUID(uid) for uid in await realtime_service.room_users(room_uid)}
        candidates = [uid for uid in candidates if uid not in active_in_room]
        if not candidates:
            return

        online_uids = await _online_members(candidates)
        if not online_uids:
            return

        preference_result = await db.execute(
            select(MessageNotificationPreference).where(
                MessageNotificationPreference.account_uid.in_(online_uids)
            )
        )
        preference_map = {
            item.account_uid: message_notification_preference_projection(item)
            for item in preference_result.scalars().all()
        }

        common_payload = {
            "type": "space_message_notification",
            "room_uid": str(room_uid),
            "message_uid": formatted_message.get("uid"),
            "content_type": formatted_message.get("content_type"),
            "sender": formatted_message.get("sender"),
            "created_at": formatted_message.get("created_at"),
        }

        deliveries: list[tuple[UUID, dict]] = []
        for account_uid in online_uids:
            policy = message_delivery_policy(
                SURFACE_SPACE,
                online=True,
                active_context=False,
                preferences=preference_map.get(account_uid),
            )
            if not policy["notify_in_app"] and not policy["play_sound"]:
                continue
            deliveries.append(
                (
                    account_uid,
                    {**common_payload, "notification": policy},
                )
            )

        for index in range(0, len(deliveries), _DELIVERY_BATCH_SIZE):
            batch = deliveries[index:index + _DELIVERY_BATCH_SIZE]
            results = await asyncio.gather(
                *(private_manager.send_to_user(uid, payload) for uid, payload in batch),
                return_exceptions=True,
            )
            for (uid, _), result in zip(batch, results):
                if isinstance(result, Exception):
                    logger.warning("Could not publish Space message alert for account=%s", uid)
    except Exception:
        logger.exception("Space message alert fan-out failed; canonical room message remains persisted")
