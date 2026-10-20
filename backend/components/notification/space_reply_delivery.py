"""Case-safe personal Space reply notifications (not an all-messages engagement blast).

Room reply must reference an actual parent IN THE SAME room, authored by an
active Account member who is neither sender nor blocked. Evidence never includes
message plaintext or peer handles. Ledger dedupe is immutable per reply UID.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from components.identity.model import Account, AccountRelationship
from components.message.model import Message
from components.notification.model import (
    ExternalDeliveryLedger, MessageNotificationPreference, UserNotification,
    NativePushDevice, WebPushSubscription,
)
from components.room.model import Room
from components.space.model import SpaceMembership
from socket_manager import private_manager
from utils.logger import setup_logger

logger = setup_logger(__name__)
SPACE_REPLY_KIND = "space_reply"


def space_reply_push_payload(room_uid: UUID) -> dict[str, str]:
    return {
        "type": "space_reply",
        "title": "Ответ в пространстве PubChat",
        "body": "Ответили на ваше сообщение.",
        "url": f"/spaces/{room_uid}",
        "room_uid": str(room_uid),
        "tag": f"pubchat-space-reply:{room_uid}",
    }


async def eligible_space_reply(
    db: AsyncSession, room_uid: UUID, sender_account_uid: UUID, recipient_account_uid: UUID,
) -> bool:
    if sender_account_uid == recipient_account_uid:
        return False
    room = await db.get(Room, room_uid)
    if room is None or not room.is_active:
        return False
    membership = (await db.execute(
        select(SpaceMembership.uid).where(
            SpaceMembership.room_uid == room_uid,
            SpaceMembership.account_uid == recipient_account_uid,
            SpaceMembership.status == "active",
        ).limit(1)
    )).scalar_one_or_none()
    if membership is None:
        return False
    blocked = (await db.execute(
        select(AccountRelationship.id).where(
            AccountRelationship.relation_type == "block",
            or_(
                and_(AccountRelationship.from_account_uid == sender_account_uid,
                     AccountRelationship.to_account_uid == recipient_account_uid),
                and_(AccountRelationship.from_account_uid == recipient_account_uid,
                     AccountRelationship.to_account_uid == sender_account_uid),
            ),
        ).limit(1)
    )).scalar_one_or_none()
    return blocked is None


async def queue_space_reply(
    db: AsyncSession, *, room_uid: UUID, sender_legacy_uid: UUID, formatted_message: dict,
) -> UUID | None:
    """Persist personal reply once; never leak other-room references or original content."""
    reply = formatted_message.get("reply_to")
    if not isinstance(reply, dict) or not reply.get("uid") or not formatted_message.get("uid"):
        return None
    try:
        reply_uid = UUID(str(reply["uid"]))
        message_uid = UUID(str(formatted_message["uid"]))
    except (ValueError, TypeError, AttributeError):
        return None

    parent = await db.get(Message, reply_uid)
    if parent is None or parent.room_uid != room_uid or parent.author_uid == sender_legacy_uid:
        return None
    sender_account = (await db.execute(
        select(Account.uid).where(
            Account.legacy_user_uid == sender_legacy_uid,
            Account.status == "active",
            Account.deleted_at.is_(None),
        ).limit(1)
    )).scalar_one_or_none()
    recipient_account = (await db.execute(
        select(Account.uid).where(
            Account.legacy_user_uid == parent.author_uid,
            Account.status == "active",
            Account.deleted_at.is_(None),
        ).limit(1)
    )).scalar_one_or_none()
    if sender_account is None or recipient_account is None:
        return None
    if not await eligible_space_reply(db, room_uid, sender_account, recipient_account):
        return None

    current = datetime.utcnow()
    record = (
        insert(UserNotification)
        .values(
            account_uid=recipient_account, kind=SPACE_REPLY_KIND,
            dedupe_key=f"reply:{message_uid}",
            title="Ответ на ваше сообщение",
            body="В пространстве ответили на ваше сообщение.",
            context_room_uid=room_uid,
            created_at=current,
        )
        .on_conflict_do_nothing(constraint="uq_user_notification_dedupe")
        .returning(UserNotification.uid)
    )
    # Record the reference before queuing external pushes to avoid a notification
    # that cannot be found in the user's in-app inbox.
    notif_uid = (await db.execute(record)).scalar_one_or_none()
    if notif_uid is None:
        await db.rollback()
        return recipient_account

    preferences = await db.get(MessageNotificationPreference, recipient_account)
    channels = []
    if preferences and preferences.web_push_space:
        existing = (await db.execute(
            select(WebPushSubscription.uid).where(WebPushSubscription.account_uid == recipient_account).limit(1)
        )).scalar_one_or_none()
        if existing:
            channels.append("web_push")
    if preferences and preferences.native_push_space:
        existing = (await db.execute(
            select(NativePushDevice.uid).where(
                NativePushDevice.account_uid == recipient_account,
                NativePushDevice.revoked_at.is_(None),
            ).limit(1)
        )).scalar_one_or_none()
        if existing:
            channels.append("native_push")

    for channel in channels:
        await db.execute(
            insert(ExternalDeliveryLedger).values(
                account_uid=recipient_account,
                channel=channel,
                aggregate_key=f"space-reply:{notif_uid}",
                dedupe_key=f"space-reply:{notif_uid}",
                status="pending", unread_count=1, dialog_count=1,
                attempt_count=0, next_attempt_at=current,
                created_at=current, updated_at=current,
            ).on_conflict_do_nothing(constraint="uq_external_delivery_dedupe")
        )
    await db.commit()

    try:
        await private_manager.send_to_user(recipient_account, {
            "type": "space_reply_notification",
            "notification_uid": str(notif_uid),
            "room_uid": str(room_uid),
            "message_uid": str(message_uid),
            "title": "Ответ на ваше сообщение",
            "created_at": current.isoformat(),
        })
    except Exception:
        # The persisted inbox is authoritative and can be retrieved later.
        logger.warning("Realtime reply notification unavailable; durable inbox remains", exc_info=True)
    return recipient_account


async def space_reply_claim_payload(db: AsyncSession, aggregate_key: str, account_uid: UUID) -> dict | None:
    """Re-check live room membership, block and user-read state before external delivery."""
    if not aggregate_key.startswith("space-reply:"):
        return None
    try:
        uid = UUID(aggregate_key.split(":", 1)[1])
    except (TypeError, ValueError):
        return None
    item = await db.get(UserNotification, uid)
    if item is None or item.account_uid != account_uid or item.kind != SPACE_REPLY_KIND or item.read_at is not None:
        return None
    if item.context_room_uid is None or not item.dedupe_key.startswith("reply:"):
        return None
    try:
        message_uid = UUID(item.dedupe_key.split(":", 1)[1])
    except (TypeError, ValueError):
        return None
    message = await db.get(Message, message_uid)
    if message is None or message.room_uid != item.context_room_uid or not message.reply_to_uid:
        return None
    sender_account_uid = (await db.execute(
        select(Account.uid).where(
            Account.legacy_user_uid == message.author_uid,
            Account.status == "active", Account.deleted_at.is_(None),
        ).limit(1)
    )).scalar_one_or_none()
    if sender_account_uid is None or not await eligible_space_reply(
        db, item.context_room_uid, sender_account_uid, account_uid
    ):
        return None
    return space_reply_push_payload(item.context_room_uid)
