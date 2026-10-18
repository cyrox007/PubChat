from datetime import datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from components.decorators.db import get_realtime_session, release_realtime_session
from components.message.model import Message
from components.moderation.policy import assert_allowed
from components.moderation.abuse_signals import record_rate_limit_signal
from components.notification.space_message_delivery import notify_online_space_members
from components.realtime import realtime_service
from components.room.model import Room, RoomBan, RoomMember
from components.user.model import Penalty
from settings import config
from socket_manager import room_manager as manager
from utils.file_handler import (
    remove_saved_file,
    save_message_files,
    save_message_voice,
)
from utils.logger import setup_logger

logger = setup_logger(__name__)


async def initialize_websocket(
    websocket: WebSocket,
    db_session: AsyncSession,
    room_uid: UUID,
    user_uid: UUID,
) -> bool:
    if await RoomBan.is_user_banned(db_session, room_uid, user_uid):
        ban_info = await RoomBan.get_active_ban_info(db_session, room_uid, user_uid)
        reason = "Доступ к пространству ограничен"
        if ban_info and ban_info.get("reason"):
            reason = f"{reason}: {ban_info['reason']}"
        await websocket.close(code=4001, reason=reason[:120])
        return False

    room = await Room.get_room_by_uid(db_session, room_uid)
    if not room or not room.is_active:
        logger.warning("Пространство не найдено: %s", room_uid)
        await websocket.close(code=1008, reason="Space not found")
        return False

    await manager.connect_to_room(websocket, room_uid, user_uid)
    await manager.update_user_activity(db_session, user_uid)

    active_mute = await Penalty.get_active_mute(db_session, user_uid)
    if active_mute:
        await websocket.send_json(
            {
                "type": "mute_status",
                "status": "muted",
                "details": {
                    "expires_at": active_mute["expires_at"],
                    "reason": active_mute["reason"],
                },
            }
        )

    await send_initial_data(websocket, db_session, room_uid)
    return True


async def send_initial_data(
    websocket: WebSocket,
    db_session: AsyncSession,
    room_uid: UUID,
) -> None:
    room_info = await Room.get_room_with_details(db_session, room_uid)
    if not room_info:
        return

    await websocket.send_json({"type": "room_info", "room": room_info})

    # Re-send a recent window after reconnect. The SPA de-duplicates by the
    # canonical server uid and the client event id (`frontId`).
    last_messages = await Message.get_last_messages(db_session, room_uid, limit=20)
    await websocket.send_json(
        {
            "type": "initial_data",
            "messages": last_messages,
            "resume": True,
        }
    )


async def _rate_limit_message(websocket: WebSocket, user_uid: UUID, db_session: AsyncSession, room_uid: UUID) -> bool:
    allowed = await realtime_service.allow_action(
        user_uid=user_uid,
        bucket="space-message",
        limit=config.REALTIME_MESSAGE_RATE_LIMIT,
        window_seconds=config.REALTIME_MESSAGE_RATE_WINDOW_SECONDS,
    )
    if allowed:
        return True

    try:
        await record_rate_limit_signal(
            db_session,
            legacy_user_uid=user_uid,
            surface="space",
            scope_uid=room_uid,
        )
    except Exception:
        logger.exception("Failed to record Space message abuse signal")

    await websocket.send_json(
        {
            "type": "rate_limited",
            "scope": "message",
            "retry_after": config.REALTIME_MESSAGE_RATE_WINDOW_SECONDS,
        }
    )
    return False


async def _enforce_capability(
    websocket: WebSocket,
    db_session: AsyncSession,
    user_uid: UUID,
    capability: str,
    room_uid: UUID,
    front_id: str | None,
) -> bool:
    try:
        await assert_allowed(
            db_session,
            user_uid,
            capability,
            scope_type="space",
            scope_uid=room_uid,
        )
        return True
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {"error_type": "capability_restricted"}
        await websocket.send_json({"type": "error", "frontId": front_id, **detail})
        return False


def _event_scope(room_uid: UUID) -> str:
    return f"space-message:{room_uid}"


async def _claim_client_event(
    websocket: WebSocket,
    room_uid: UUID,
    user_uid: UUID,
    front_id: str | None,
) -> bool:
    claimed = await realtime_service.claim_event(
        user_uid=user_uid,
        scope=_event_scope(room_uid),
        event_id=front_id,
    )
    if claimed:
        return True

    await websocket.send_json(
        {
            "type": "duplicate_ignored",
            "frontId": front_id,
            "scope": "space_message",
        }
    )
    return False


async def _release_client_event(room_uid: UUID, user_uid: UUID, front_id: str | None) -> None:
    await realtime_service.release_event(
        user_uid=user_uid,
        scope=_event_scope(room_uid),
        event_id=front_id,
    )


async def _notify_online_members(
    db_session: AsyncSession,
    room_uid: UUID,
    user_uid: UUID,
    formatted_message: dict,
) -> None:
    # Secondary alerts are deliberately best-effort. The canonical room message
    # has already been persisted and broadcast; notification failure must never
    # turn a successful send into a client-visible retry/duplicate situation.
    await notify_online_space_members(
        db_session,
        room_uid=room_uid,
        sender_uid=user_uid,
        formatted_message=formatted_message,
    )


async def process_incoming_messages(
    websocket: WebSocket,
    room_uid: UUID,
    user_uid: UUID,
    db_session: AsyncSession,
) -> None:
    while True:
        await release_realtime_session(db_session)
        data = await websocket.receive_json()
        frame_type = data.get("type")

        if frame_type in {"heartbeat", "pong"}:
            await manager.touch_connection(websocket)
            continue

        await manager.touch_connection(websocket)

        if frame_type == "moderator_action":
            response = await handle_moderator_action(data, db_session, user_uid)
            await manager.broadcast_to_room(room_uid, response)
            await manager.update_user_activity(db_session, user_uid)
            continue

        if frame_type == "ban_user":
            response = await handle_ban_user(data, db_session, room_uid, user_uid)
            if response:
                await manager.broadcast_to_room(room_uid, response)
            await manager.update_user_activity(db_session, user_uid)
            continue

        front_id = data.get("frontId")
        if not await _enforce_capability(
            websocket,
            db_session,
            user_uid,
            "space.chat.send",
            room_uid,
            front_id,
        ):
            continue

        content_type = data.get("content_type", "text")
        if content_type in {"file", "image", "video", "voice", "audio"}:
            if not await _enforce_capability(
                websocket,
                db_session,
                user_uid,
                "media.upload",
                room_uid,
                front_id,
            ):
                continue

        if not await _rate_limit_message(websocket, user_uid, db_session, room_uid):
            continue

        if content_type == "text":
            await handle_text_message(data, room_uid, user_uid, db_session, websocket)
        elif content_type in {"file", "image", "video"}:
            await handle_file_message(data, room_uid, user_uid, db_session, websocket)
        elif content_type in {"voice", "audio"}:
            await handle_audio_message(data, room_uid, user_uid, db_session, websocket)
        else:
            await websocket.send_json(
                {
                    "type": "error",
                    "error_type": "unsupported_content_type",
                    "frontId": front_id,
                }
            )

        await manager.update_user_activity(db_session, user_uid)


async def handle_text_message(
    data: dict,
    room_uid: UUID,
    user_uid: UUID,
    db_session: AsyncSession,
    websocket: WebSocket,
) -> None:
    content = data.get("content")
    if not isinstance(content, str) or not content.strip():
        return

    front_id = data.get("frontId")
    if not await _claim_client_event(websocket, room_uid, user_uid, front_id):
        return

    try:
        formatted_message = await Message.create_message(
            db_session,
            {
                "content": content,
                "content_type": "text",
                "sender_uid": str(user_uid),
                "room_uid": str(room_uid),
                "reply_to_uid": data.get("reply_to_uid"),
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        formatted_message["frontId"] = front_id
        await manager.broadcast_to_room(room_uid, formatted_message)
        await _notify_online_members(db_session, room_uid, user_uid, formatted_message)
    except Exception:
        await _release_client_event(room_uid, user_uid, front_id)
        raise


async def handle_file_message(
    data: dict,
    room_uid: UUID,
    user_uid: UUID,
    db_session: AsyncSession,
    websocket: WebSocket,
) -> None:
    media_metadata = data.get("media_metadata") or {}
    files = media_metadata.get("files")
    if not files:
        return

    front_id = data.get("frontId")
    if not await _claim_client_event(websocket, room_uid, user_uid, front_id):
        return

    saved_files: list[dict] = []
    message_persisted = False
    try:
        saved_files = save_message_files(
            files,
            content_type=data.get("content_type", "file"),
        )
        uploaded_bytes = sum(int(item["size"]) for item in saved_files)
        allowed_media_bytes = await realtime_service.allow_cost(
            user_uid,
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

        formatted_message = await Message.create_message(
            db_session,
            {
                "content": data.get("content", ""),
                "content_type": data.get("content_type", "file"),
                "sender_uid": str(user_uid),
                "room_uid": str(room_uid),
                "media_metadata": {"files": saved_files},
                "reply_to_uid": data.get("reply_to_uid"),
            },
        )
        message_persisted = True
        formatted_message["frontId"] = front_id
        await manager.broadcast_to_room(room_uid, formatted_message)
        await _notify_online_members(db_session, room_uid, user_uid, formatted_message)
    except HTTPException as exc:
        if not message_persisted:
            for item in saved_files:
                remove_saved_file(item.get("url"))
        await _release_client_event(room_uid, user_uid, front_id)
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        await websocket.send_json(
            {
                "type": "error",
                "error_type": detail.get("error_type", "attachments_failed"),
                "frontId": front_id,
            }
        )
    except Exception:
        if not message_persisted:
            for item in saved_files:
                remove_saved_file(item.get("url"))
        await _release_client_event(room_uid, user_uid, front_id)
        logger.exception("Не удалось сохранить Space attachment message")
        await websocket.send_json(
            {
                "type": "error",
                "error_type": "attachments_failed",
                "frontId": front_id,
            }
        )


async def handle_audio_message(
    data: dict,
    room_uid: UUID,
    user_uid: UUID,
    db_session: AsyncSession,
    websocket: WebSocket,
) -> None:
    media_metadata = data.get("media_metadata") or {}
    voice = media_metadata.get("voice")
    files = media_metadata.get("files")
    if not voice and not (isinstance(files, list) and files):
        return

    front_id = data.get("frontId")
    if not await _claim_client_event(websocket, room_uid, user_uid, front_id):
        return

    saved_audio = None
    message_persisted = False
    try:
        if voice:
            saved_audio = save_message_voice(voice)
        else:
            saved_files = save_message_files(
                files,
                content_type="audio",
            )
            if len(saved_files) != 1:
                for item in saved_files:
                    remove_saved_file(item.get("url"))
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error_type": "upload_audio_count_invalid",
                        "message": "Аудиосообщение должно содержать один файл.",
                    },
                )
            saved_audio = saved_files[0]

        saved_audio_url = saved_audio["url"]
        allowed_media_bytes = await realtime_service.allow_cost(
            user_uid,
            "media-upload-bytes",
            int(saved_audio["size"]),
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

        formatted_message = await Message.create_message(
            db_session,
            {
                "content": saved_audio_url,
                "content_type": "audio",
                "sender_uid": str(user_uid),
                "room_uid": str(room_uid),
                "reply_to_uid": data.get("reply_to_uid"),
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        message_persisted = True
        formatted_message["frontId"] = front_id
        await manager.broadcast_to_room(room_uid, formatted_message)
        await _notify_online_members(db_session, room_uid, user_uid, formatted_message)
    except HTTPException as exc:
        if not message_persisted and saved_audio:
            remove_saved_file(saved_audio.get("url"))
        await _release_client_event(room_uid, user_uid, front_id)
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        await websocket.send_json(
            {
                "type": "error",
                "error_type": detail.get("error_type", "audio_failed"),
                "frontId": front_id,
            }
        )
    except Exception:
        if not message_persisted and saved_audio:
            remove_saved_file(saved_audio.get("url"))
        await _release_client_event(room_uid, user_uid, front_id)
        logger.exception("Не удалось обработать audio frame")
        await websocket.send_json(
            {
                "type": "error",
                "error_type": "audio_failed",
                "frontId": front_id,
            }
        )


async def handle_moderator_action(
    data: dict,
    db_session: AsyncSession,
    user_uid: UUID,
) -> dict:
    try:
        room_uid = UUID(str(data["room_uid"]))
        target_user_uid = UUID(str(data["target_user_uid"]))
        action = data["action"]

        room = await Room.get_room_by_uid(db_session, room_uid)
        if not room or str(room.owner_uid) != str(user_uid):
            return {
                "type": "error",
                "error_type": "space_owner_required",
                "message": "Только владелец пространства может управлять ролями",
            }

        if action == "add_moderator":
            await Room.add_moderator(db_session, room_uid, target_user_uid)
            event_type = "moderator_added"
        elif action == "remove_moderator":
            await Room.remove_moderator(db_session, room_uid, target_user_uid)
            event_type = "moderator_removed"
        else:
            return {"type": "error", "error_type": "unknown_moderator_action"}

        moderators = await RoomMember.get_moderators(db_session, room_uid)
        return {
            "type": event_type,
            "room_uid": str(room_uid),
            "target_user_uid": str(target_user_uid),
            "moderators": [str(item) for item in moderators],
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception:
        logger.exception("Ошибка изменения scoped роли пространства")
        return {"type": "error", "error_type": "moderator_action_failed"}


async def handle_ban_user(
    data: dict,
    db_session: AsyncSession,
    room_uid: UUID,
    user_uid: UUID,
) -> dict:
    try:
        target_user_uid = UUID(str(data["target_user_uid"]))
        reason = str(data.get("reason") or "Нарушение правил пространства")[:500]
        ban_duration = None if data.get("permanent", False) else timedelta(days=7)

        room = await Room.get_room_by_uid(db_session, room_uid)
        if not room:
            return {"type": "error", "error_type": "space_not_found"}

        is_owner = str(room.owner_uid) == str(user_uid)
        is_moderator = await RoomMember.is_moderator(db_session, room_uid, user_uid)
        if not (is_owner or is_moderator):
            return {"type": "error", "error_type": "space_moderator_required"}

        ban = await RoomBan.ban_user(
            db_session,
            room_uid=room_uid,
            user_uid=target_user_uid,
            banned_by_uid=user_uid,
            reason=reason,
            ban_duration=ban_duration,
        )

        notification = {
            "type": "user_banned",
            "room_uid": str(room_uid),
            "target_user_uid": str(target_user_uid),
            "restricted_by": str(user_uid),
            "reason": reason,
            "expires_at": ban.expires_at.isoformat() if ban.expires_at else None,
            "permanent": ban.expires_at is None,
            "timestamp": datetime.utcnow().isoformat(),
        }
        await manager.disconnect_user_from_room(room_uid, target_user_uid, reason=reason)
        return notification
    except (KeyError, ValueError):
        return {"type": "error", "error_type": "invalid_restriction_target"}
    except Exception:
        logger.exception("Ошибка ограничения доступа к пространству")
        return {"type": "error", "error_type": "space_restriction_failed"}


@get_realtime_session
async def handle_websocket_connection(
    websocket: WebSocket,
    room_uid: UUID | str,
    user: dict,
    db_session: AsyncSession = None,
):
    normalized_room_uid = UUID(str(room_uid))
    user_uid = UUID(user["user_uid"])
    connected = False

    try:
        connected = await initialize_websocket(
            websocket,
            db_session,
            normalized_room_uid,
            user_uid,
        )
        if not connected:
            return
        await process_incoming_messages(
            websocket,
            normalized_room_uid,
            user_uid,
            db_session,
        )
    except WebSocketDisconnect:
        logger.info("Room realtime disconnected: user=%s room=%s", user_uid, normalized_room_uid)
    except Exception:
        logger.exception("Room realtime handler failed")
        try:
            await websocket.close(code=1011, reason="Realtime room error")
        except Exception:
            pass
    finally:
        if connected:
            await manager.disconnect(websocket, normalized_room_uid)
