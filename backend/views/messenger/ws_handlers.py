from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from components.decorators.db import get_realtime_session, release_realtime_session
from components.identity.model import AccountRelationship, Persona, PrivacySettings
from components.message.model import PrivateMessage
from components.moderation.policy import assert_allowed
from components.moderation.lexicon_service import inspect_plaintext_write
from components.moderation.abuse_signals import detect_dm_recipient_burst, record_rate_limit_signal
from components.notification.message_delivery import (
    SURFACE_MESSENGER,
    get_message_notification_preferences,
    message_delivery_policy,
)
from components.notification.web_push import queue_messenger_web_push
from components.realtime import realtime_service
from components.realtime.active_context import active_context_service
from components.room.model import RoomMember
from components.user.model import User
from database import Database
from settings import config
from socket_manager import private_manager
from utils.file_handler import remove_saved_file, save_message_files, save_message_voice
from utils.logger import setup_logger

logger = setup_logger(__name__)


def _persist_private_message_media(
    content_type: str,
    media_metadata: dict | None,
) -> tuple[dict | None, list[str], int]:
    metadata = media_metadata if isinstance(media_metadata, dict) else {}

    if content_type in {"file", "image", "video", "audio"}:
        saved = save_message_files(
            metadata.get("files"),
            content_type=content_type,
        )
        return (
            {"files": saved},
            [item["url"] for item in saved],
            sum(int(item["size"]) for item in saved),
        )

    if content_type == "voice":
        voice = metadata.get("voice")
        if not voice:
            raise HTTPException(
                status_code=400,
                detail={"error_type": "upload_voice_missing", "message": "Голосовое сообщение пустое."},
            )
        saved = save_message_voice(voice)
        return {"voice": saved["url"]}, [saved["url"]], int(saved["size"])

    return media_metadata, [], 0


async def initialize_messenger_connection(
    websocket: WebSocket,
    user_uid: UUID,
    db_session: AsyncSession,
) -> None:
    await private_manager.connect_to_messenger(websocket, user_uid)
    await User.update_last_online(db_session, user_uid)


async def _dm_allowed(
    db_session: AsyncSession,
    sender_uid: UUID,
    receiver_uid: UUID,
) -> bool:
    if sender_uid == receiver_uid:
        return True

    blocked = await db_session.execute(
        select(AccountRelationship.id)
        .where(
            AccountRelationship.relation_type == "block",
            or_(
                and_(
                    AccountRelationship.from_account_uid == sender_uid,
                    AccountRelationship.to_account_uid == receiver_uid,
                ),
                and_(
                    AccountRelationship.from_account_uid == receiver_uid,
                    AccountRelationship.to_account_uid == sender_uid,
                ),
            ),
        )
        .limit(1)
    )
    if blocked.scalar_one_or_none() is not None:
        return False

    policy_result = await db_session.execute(
        select(PrivacySettings.dm_policy)
        .join(Persona, Persona.uid == PrivacySettings.persona_uid)
        .where(
            Persona.account_uid == receiver_uid,
            Persona.is_primary.is_(True),
        )
        .limit(1)
    )
    dm_policy = policy_result.scalar_one_or_none() or "shared_spaces"

    if dm_policy == "everyone":
        return True
    if dm_policy == "nobody":
        return False

    if dm_policy == "mutual":
        reciprocal = await db_session.execute(
            select(func.count(AccountRelationship.id)).where(
                AccountRelationship.relation_type == "friend",
                or_(
                    and_(
                        AccountRelationship.from_account_uid == sender_uid,
                        AccountRelationship.to_account_uid == receiver_uid,
                    ),
                    and_(
                        AccountRelationship.from_account_uid == receiver_uid,
                        AccountRelationship.to_account_uid == sender_uid,
                    ),
                ),
            )
        )
        return (reciprocal.scalar_one() or 0) >= 2

    if dm_policy == "shared_spaces":
        shared_space = await db_session.execute(
            select(RoomMember.room_uid)
            .where(
                RoomMember.user_uid.in_([sender_uid, receiver_uid]),
                RoomMember.is_banned.is_(False),
            )
            .group_by(RoomMember.room_uid)
            .having(func.count(func.distinct(RoomMember.user_uid)) >= 2)
            .limit(1)
        )
        return shared_space.scalar_one_or_none() is not None

    return False


async def _rate_limit_message(websocket: WebSocket, user_uid: UUID, db_session: AsyncSession) -> bool:
    allowed = await realtime_service.allow_action(
        user_uid=user_uid,
        bucket="direct-message",
        limit=config.REALTIME_MESSAGE_RATE_LIMIT,
        window_seconds=config.REALTIME_MESSAGE_RATE_WINDOW_SECONDS,
    )
    if allowed:
        return True
    try:
        await record_rate_limit_signal(
            db_session,
            legacy_user_uid=user_uid,
            surface="messenger",
        )
    except Exception:
        logger.exception("Failed to record Messenger abuse signal")
    await websocket.send_json(
        {
            "type": "rate_limited",
            "scope": "direct_message",
            "retry_after": config.REALTIME_MESSAGE_RATE_WINDOW_SECONDS,
        }
    )
    return False


def _dm_event_scope(receiver_uid: UUID) -> str:
    return f"direct-message:{receiver_uid}"


async def _enforce_capability(
    websocket: WebSocket,
    db_session: AsyncSession,
    user_uid: UUID,
    capability: str,
    front_id: str | None,
) -> bool:
    try:
        await assert_allowed(db_session, user_uid, capability)
        return True
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {"error_type": "capability_restricted"}
        await websocket.send_json({"type": "error", "frontId": front_id, **detail})
        return False


async def _set_active_dialog_context(
    websocket: WebSocket,
    user_uid: UUID,
    dialog_uid: UUID,
) -> None:
    connection_id = private_manager.connection_ids.get(websocket)
    previous = private_manager.get_active_dialog(websocket)
    if connection_id and previous and previous != dialog_uid:
        await active_context_service.clear_messenger(connection_id, user_uid, previous)
    private_manager.set_active_dialog(websocket, dialog_uid)
    if connection_id:
        await active_context_service.set_messenger(connection_id, user_uid, dialog_uid)


async def _clear_active_dialog_context(websocket: WebSocket, user_uid: UUID) -> None:
    connection_id = private_manager.connection_ids.get(websocket)
    previous = private_manager.get_active_dialog(websocket)
    if connection_id and previous:
        await active_context_service.clear_messenger(connection_id, user_uid, previous)
    private_manager.active_dialogs.pop(websocket, None)


async def _refresh_active_dialog_context(websocket: WebSocket, user_uid: UUID) -> None:
    connection_id = private_manager.connection_ids.get(websocket)
    dialog_uid = private_manager.get_active_dialog(websocket)
    if connection_id and dialog_uid:
        await active_context_service.set_messenger(connection_id, user_uid, dialog_uid)


async def handle_private_messages(
    websocket: WebSocket,
    user_uid: UUID,
    db_session: AsyncSession,
) -> None:
    while True:
        await release_realtime_session(db_session)
        data = await websocket.receive_json()
        action = data.get("action")
        frame_type = data.get("type")

        if frame_type in {"heartbeat", "pong"} or action == "heartbeat":
            await private_manager.touch_connection(websocket)
            await _refresh_active_dialog_context(websocket, user_uid)
            continue

        await private_manager.touch_connection(websocket)

        if action == "send_message":
            if await _rate_limit_message(websocket, user_uid, db_session):
                await handle_send_private_message(data, user_uid, db_session, websocket)
        elif action == "mark_message_as_read":
            await handle_mark_as_read(data, user_uid, db_session, websocket)
        elif action == "get_conversation":
            await handle_get_conversation(data, user_uid, db_session, websocket)
        elif action == "set_active_dialog":
            try:
                dialog_uid = UUID(str(data.get("other_user_uid")))
            except (TypeError, ValueError):
                await websocket.send_json({"type": "error", "error_type": "invalid_active_dialog"})
                continue
            await _set_active_dialog_context(websocket, user_uid, dialog_uid)
        elif action == "clear_active_dialog":
            await _clear_active_dialog_context(websocket, user_uid)
        elif action == "subscribe_status":
            target_uids = [UUID(uid) for uid in data.get("userIds", [])]
            await private_manager.subscribe_to_status(user_uid, target_uids)
        elif action == "unsubscribe_status":
            target_uids = [UUID(uid) for uid in data.get("userIds", [])]
            await private_manager.unsubscribe_from_status(user_uid, target_uids)
        else:
            await websocket.send_json({"type": "error", "error_type": "unknown_action"})

        await private_manager.update_user_activity(db_session, user_uid)


async def handle_send_private_message(
    data: dict,
    sender_uid: UUID,
    db_session: AsyncSession,
    websocket: WebSocket,
) -> None:
    try:
        receiver_uid = UUID(str(data.get("receiver_uid")))
    except (TypeError, ValueError):
        await websocket.send_json(
            {
                "type": "error",
                "error_type": "invalid_receiver",
                "frontId": data.get("frontId"),
            }
        )
        return

    front_id = data.get("frontId")
    if not await _enforce_capability(
        websocket,
        db_session,
        sender_uid,
        "messenger.send",
        front_id,
    ):
        return

    content_type = data.get("content_type", "text")
    if content_type in {"file", "image", "video", "voice", "audio"}:
        if not await _enforce_capability(
            websocket,
            db_session,
            sender_uid,
            "media.upload",
            front_id,
        ):
            return

    if not await _dm_allowed(db_session, sender_uid, receiver_uid):
        await websocket.send_json(
            {
                "type": "error",
                "error_type": "dm_not_allowed",
                "frontId": front_id,
            }
        )
        return

    scope = _dm_event_scope(receiver_uid)
    claimed = await realtime_service.claim_event(
        user_uid=sender_uid,
        scope=scope,
        event_id=front_id,
    )
    if not claimed:
        await websocket.send_json(
            {
                "type": "duplicate_ignored",
                "scope": "direct_message",
                "frontId": front_id,
            }
        )
        return

    saved_upload_urls: list[str] = []
    message_persisted = False
    try:
        if isinstance(data.get("content"), str) and data["content"].strip():
            if content_type == "text":
                moderation_surface = "messenger_plaintext"
            elif content_type in {"file", "image", "video", "voice", "audio"}:
                moderation_surface = "media_caption"
            else:
                moderation_surface = None  # E2EE and unknown envelopes must never be inspected.
            if moderation_surface is not None:
                await inspect_plaintext_write(
                    db_session, data["content"], surface=moderation_surface, operation="send"
                )
        persisted_media_metadata, saved_upload_urls, uploaded_bytes = _persist_private_message_media(
            content_type,
            data.get("media_metadata"),
        )
        if uploaded_bytes:
            allowed_media_bytes = await realtime_service.allow_cost(
                sender_uid,
                "media-upload-bytes",
                uploaded_bytes,
                config.MEDIA_UPLOAD_RATE_LIMIT_BYTES,
                config.MEDIA_UPLOAD_RATE_WINDOW_SECONDS,
            )
            if not allowed_media_bytes:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error_type": "media_upload_rate_limited",
                        "message": "Слишком большой объём вложений за короткое время.",
                    },
                )

        formatted_message = await PrivateMessage.create_private_message(
            db_session,
            {
                "content": data.get("content"),
                "content_type": content_type,
                "sender_uid": str(sender_uid),
                "receiver_uid": str(receiver_uid),
                "media_metadata": persisted_media_metadata,
            },
        )
        message_persisted = True
        formatted_message["frontId"] = front_id

        try:
            await detect_dm_recipient_burst(
                db_session,
                sender_legacy_uid=sender_uid,
            )
        except Exception:
            logger.exception("Failed to evaluate Messenger recipient-burst signal")

        sender_message = {
            **formatted_message,
            "notification": {
                "surface": SURFACE_MESSENGER,
                "notify_in_app": False,
                "play_sound": False,
                "active_context": True,
            },
        }
        await private_manager.send_to_user(sender_uid, sender_message)

        if receiver_uid != sender_uid:
            preferences = await get_message_notification_preferences(db_session, receiver_uid)
            receiver_online = await realtime_service.is_online(receiver_uid)
            receiver_active = await active_context_service.is_active(
                receiver_uid,
                SURFACE_MESSENGER,
                sender_uid,
            )
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
                    # External delivery is best-effort and must never turn a
                    # successfully persisted direct message into a send failure.
                    logger.exception("Failed to queue Messenger Web Push")

            await private_manager.send_to_user(
                receiver_uid,
                {**formatted_message, "notification": policy},
            )
    except HTTPException as exc:
        if not message_persisted:
            for url in saved_upload_urls:
                remove_saved_file(url)
        await realtime_service.release_event(sender_uid, scope, front_id)
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        await websocket.send_json(
            {
                "type": "error",
                "error_type": detail.get("error_type", "media_upload_failed"),
                "frontId": front_id,
            }
        )
    except Exception:
        if not message_persisted:
            for url in saved_upload_urls:
                remove_saved_file(url)
        await realtime_service.release_event(sender_uid, scope, front_id)
        logger.exception("Ошибка отправки private message")
        await websocket.send_json(
            {
                "type": "error",
                "error_type": "message_send_failed",
                "frontId": front_id,
            }
        )


async def handle_mark_as_read(
    data: dict,
    user_uid: UUID,
    db_session: AsyncSession,
    websocket: WebSocket,
) -> None:
    try:
        message_uid = UUID(str(data.get("message_uid")))
    except (TypeError, ValueError):
        return

    try:
        result = await db_session.execute(
            select(PrivateMessage).where(
                PrivateMessage.uid == message_uid,
                PrivateMessage.receiver_uid == user_uid,
            )
        )
        message = result.scalar_one_or_none()
        if not message:
            await websocket.send_json({"type": "error", "error_type": "read_receipt_not_allowed"})
            return

        if not message.is_read:
            message.is_read = True
            await db_session.commit()

        await private_manager.send_to_user(
            message.sender_uid,
            {
                "type": "message_read",
                "message_uid": str(message_uid),
                "read_at": datetime.utcnow().isoformat(),
            },
        )
    except Exception:
        await db_session.rollback()
        logger.exception("Ошибка read receipt")


async def handle_get_conversation(
    data: dict,
    user_uid: UUID,
    db_session: AsyncSession,
    websocket: WebSocket,
) -> None:
    try:
        other_user_uid = UUID(str(data.get("other_user_uid")))
        await _set_active_dialog_context(websocket, user_uid, other_user_uid)
        messages = await PrivateMessage.get_conversation(
            db_session,
            user1_uid=user_uid,
            user2_uid=other_user_uid,
        )
        await private_manager.send_to_specific_user(
            websocket,
            {
                "type": "conversation",
                "other_user_uid": str(other_user_uid),
                "messages": messages,
                "request_id": data.get("request_id"),
                "resume": True,
            },
        )
    except Exception:
        logger.exception("Ошибка получения conversation")
        await private_manager.send_to_specific_user(
            websocket,
            {
                "type": "error",
                "error_type": "conversation_failed",
                "request_id": data.get("request_id"),
            },
        )


@get_realtime_session
async def handle_messenger_connection(
    websocket: WebSocket,
    user: dict,
    db_session: AsyncSession = None,
):
    user_uid = UUID(user["user_uid"])
    connected = False

    try:
        await initialize_messenger_connection(websocket, user_uid, db_session)
        connected = True
        await handle_private_messages(websocket, user_uid, db_session)
    except WebSocketDisconnect:
        logger.info("Messenger realtime disconnected: user=%s", user_uid)
    except Exception:
        logger.exception("Messenger realtime handler failed")
        try:
            await websocket.close(code=1011, reason="Realtime messenger error")
        except Exception:
            pass
    finally:
        if connected:
            await _clear_active_dialog_context(websocket, user_uid)
            await private_manager.disconnect(websocket)
