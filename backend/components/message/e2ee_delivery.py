from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from components.message.e2ee_attachment import bind_encrypted_attachment
from components.message.e2ee_service import E2EE_VERSION, envelopes_for_messages, persist_envelopes, validate_encrypted_envelopes
from components.message.model import PrivateMessage
from components.moderation.abuse_signals import detect_dm_recipient_burst
from components.notification.message_delivery import SURFACE_MESSENGER, get_message_notification_preferences, message_delivery_policy
from components.notification.web_push import queue_messenger_web_push
from components.realtime import realtime_service
from components.realtime.active_context import active_context_service
from database import Database
from socket_manager import private_manager
from utils.logger import setup_logger

logger = setup_logger(__name__)


async def send_encrypted_message(
    db: AsyncSession,
    *,
    sender_uid: UUID,
    receiver_uid: UUID,
    sender_device_uid: UUID,
    front_id: str,
    envelopes: list[dict],
    attachment_uid: UUID | None = None,
) -> dict:
    scope = f"direct-message:{receiver_uid}"
    claimed = await realtime_service.claim_event(user_uid=sender_uid, scope=scope, event_id=front_id)
    if not claimed:
        return {"duplicate": True, "frontId": front_id}

    try:
        validated = await validate_encrypted_envelopes(
            db,
            sender_uid=sender_uid,
            receiver_uid=receiver_uid,
            sender_device_uid=sender_device_uid,
            raw_envelopes=envelopes,
        )
        metadata = {
            "encryption_version": E2EE_VERSION,
            "payload_kind": "attachment" if attachment_uid else "text",
        }
        if attachment_uid:
            metadata["attachment_uid"] = str(attachment_uid)
        message = PrivateMessage(
            content_type="e2ee",
            text=None,
            media_metadata=metadata,
            sender_uid=sender_uid,
            receiver_uid=receiver_uid,
        )
        db.add(message)
        await db.flush()
        if attachment_uid:
            await bind_encrypted_attachment(
                db,
                account_uid=sender_uid,
                attachment_uid=attachment_uid,
                message_uid=message.uid,
            )
        await persist_envelopes(db, message_uid=message.uid, envelopes=validated)
        await db.commit()
        await db.refresh(message, attribute_names=["sender", "receiver"])
    except Exception:
        await db.rollback()
        await realtime_service.release_event(sender_uid, scope, front_id)
        raise

    try:
        await detect_dm_recipient_burst(db, sender_legacy_uid=sender_uid)
    except Exception:
        logger.exception("Failed to evaluate encrypted Messenger recipient-burst signal")

    base = PrivateMessage.format_message(message)
    base["frontId"] = front_id
    base["encryption_version"] = E2EE_VERSION

    sender_envelopes = [
        {
            "recipient_device_uid": str(item["recipient_device_uid"]),
            "sender_device_uid": str(item["sender_device_uid"]),
            "session_id": str(item["session_id"]),
            "counter": item["counter"],
            "nonce": item["nonce"],
            "ciphertext": item["ciphertext"],
            "initial_header": item["initial_header"],
        }
        for item in validated
        if item["recipient_account_uid"] == sender_uid
    ]
    receiver_envelopes = [
        {
            "recipient_device_uid": str(item["recipient_device_uid"]),
            "sender_device_uid": str(item["sender_device_uid"]),
            "session_id": str(item["session_id"]),
            "counter": item["counter"],
            "nonce": item["nonce"],
            "ciphertext": item["ciphertext"],
            "initial_header": item["initial_header"],
        }
        for item in validated
        if item["recipient_account_uid"] == receiver_uid
    ]

    await private_manager.send_to_user(
        sender_uid,
        {
            **base,
            "envelopes": sender_envelopes,
            "notification": {
                "surface": SURFACE_MESSENGER,
                "notify_in_app": False,
                "play_sound": False,
                "active_context": True,
            },
        },
    )

    if receiver_uid != sender_uid:
        preferences = await get_message_notification_preferences(db, receiver_uid)
        receiver_online = await realtime_service.is_online(receiver_uid)
        receiver_active = await active_context_service.is_active(receiver_uid, SURFACE_MESSENGER, sender_uid)
        policy = message_delivery_policy(
            SURFACE_MESSENGER,
            online=receiver_online,
            active_context=receiver_active,
            preferences=preferences,
        )
        if policy.get("web_push_eligible"):
            try:
                async with Database.sessionmaker() as push_db:
                    await queue_messenger_web_push(
                        push_db,
                        receiver_legacy_uid=receiver_uid,
                        sender_legacy_uid=sender_uid,
                    )
            except Exception:
                logger.exception("Failed to queue encrypted Messenger Web Push")
        await private_manager.send_to_user(
            receiver_uid,
            {**base, "envelopes": receiver_envelopes, "notification": policy},
        )

    return {"duplicate": False, "message": {**base, "envelopes": sender_envelopes}}


async def history_envelopes(
    db: AsyncSession,
    *,
    account_uid: UUID,
    message_uids: list[UUID],
) -> dict[str, list[dict]]:
    result = await db.execute(
        select(PrivateMessage.uid).where(
            PrivateMessage.uid.in_(message_uids),
            or_(
                PrivateMessage.sender_uid == account_uid,
                PrivateMessage.receiver_uid == account_uid,
            ),
            PrivateMessage.content_type == "e2ee",
        )
    )
    allowed = list(result.scalars().all())
    return await envelopes_for_messages(db, message_uids=allowed, account_uid=account_uid)
