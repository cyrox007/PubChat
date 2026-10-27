from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from components.auth.middleware import auth_middle
from components.message.actions import active_room_member, edit_message, ensure_message_access, load_message, reaction_projection, soft_delete_message, toggle_reaction
from components.message.model import Message, PrivateMessage
from components.message.encryption_policy import assert_plaintext_allowed
from components.moderation.policy import assert_allowed
from components.moderation.lexicon_service import inspect_plaintext_write
from components.notification.space_reply_delivery import queue_space_reply
from components.notification.space_message_delivery import notify_online_space_members
from database import Database
from socket_manager import private_manager, room_manager
from utils.logger import setup_logger

logger = setup_logger(__name__)
from views.messenger.ws_handlers import _dm_allowed


class EditMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=1000)


class ReplyMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=1000)
    frontId: str | None = Field(default=None, min_length=1, max_length=128)


class ReactionRequest(BaseModel):
    emoji: str = Field(min_length=1, max_length=32)


class ForwardMessageRequest(BaseModel):
    target_surface: str
    target_uid: UUID


def _user_uid(current_user: dict) -> UUID:
    try:
        return UUID(str(current_user["user_uid"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=401, detail={"error_type": "invalid_account"}) from exc


def _standard_frame(surface: str, message, *, overrides: dict | None = None) -> dict:
    overrides = overrides or {}
    metadata = dict(message.media_metadata or {})
    if "media_metadata" in overrides:
        metadata = dict(overrides["media_metadata"] or {})
    if surface == "room":
        # Do not send a partial sender object on update frames: the client merges
        # by UID and keeps its already hydrated Persona fields.
        return {
            "type": "message",
            "uid": str(message.uid),
            "frontId": getattr(message, "front_id", None),
            "content": overrides.get("content", message.text or ""),
            "content_type": overrides.get("content_type", message.content_type),
            "media_metadata": metadata,
            "room_uid": str(message.room_uid),
            "created_at": message.created_at.isoformat(),
        }
    return {
        "type": "private_message",
        "uid": str(message.uid),
        "frontId": getattr(message, "front_id", None),
        "content": overrides.get("content", message.text or ""),
        "content_type": overrides.get("content_type", message.content_type),
        "media_metadata": metadata,
        "sender_uid": str(message.sender_uid),
        "receiver_uid": str(message.receiver_uid),
        "is_read": bool(message.is_read),
        "created_at": message.created_at.isoformat(),
    }


async def _publish_frame(surface: str, message, frame: dict) -> None:
    if surface == "room":
        await room_manager.broadcast_to_room(message.room_uid, frame)
    else:
        await private_manager.send_to_user(message.sender_uid, frame)
        if message.receiver_uid != message.sender_uid:
            await private_manager.send_to_user(message.receiver_uid, frame)


def _reply_snapshot(surface: str, source) -> dict:
    return {
        "uid": str(source.uid),
        "content": source.text or "",
        "content_type": source.content_type,
        "sender": {
            "uid": str(source.author_uid if surface == "room" else source.sender_uid),
            "name": "Участник PubChat",
        },
        "created_at": source.created_at.isoformat() if source.created_at else None,
    }


async def _publish_space_reply_after_commit(
    db: AsyncSession, *, room_uid: UUID, sender_uid: UUID, created: dict,
) -> None:
    """Match the room WebSocket path for replies sent via Android HTTP.

    A saved message must survive an unavailable realtime or push service.
    This creates the same durable personal reply notification + pending push
    ledger as the WebSocket path, but never notifies for unrelated room posts.
    """
    # No concrete HTTP socket to acknowledge; the HTTP 201 response itself
    # carries the canonical uid. Keep post-commit Redis and notification work
    # bounded and separate from the request's transaction session.
    import asyncio
    from settings import config
    timeout = max(0.1, config.REALTIME_SEND_TIMEOUT_SECONDS)
    try:
        await asyncio.wait_for(room_manager.broadcast_to_room(room_uid, created), timeout=timeout)
    except Exception:
        logger.exception("Room reply saved but realtime broadcast failed")
    try:
        async with Database.sessionmaker()() as notification_db:
            recipient = await asyncio.wait_for(queue_space_reply(
                notification_db, room_uid=room_uid, sender_legacy_uid=sender_uid,
                formatted_message=created,
            ), timeout=timeout)
            await asyncio.wait_for(notify_online_space_members(
                notification_db, room_uid=room_uid, sender_uid=sender_uid,
                formatted_message=created, exclude_uids={recipient} if recipient else None,
            ), timeout=timeout)
    except Exception:
        logger.exception("Room reply saved but secondary notifications unavailable")


def install(app: FastAPI):
    router = APIRouter(prefix="/messages/v2", tags=["messages-v2"])

    @router.patch("/{surface}/{message_uid}")
    async def patch_message(surface: str, message_uid: UUID, payload: EditMessageRequest, current_user: dict = Depends(auth_middle), db: AsyncSession = Depends(Database.session_generator)):
        user_uid = _user_uid(current_user)
        await assert_allowed(db, user_uid, "messenger.send" if surface == "messenger" else "space.chat.send")
        message = await load_message(db, surface, message_uid)
        if surface == "messenger":
            await ensure_message_access(db, surface, message, user_uid, write=True)
            if message.content_type == "e2ee":
                raise HTTPException(status_code=409, detail={"error_type": "encrypted_message_edit_requires_e2ee"})
            other_uid = message.receiver_uid if message.sender_uid == user_uid else message.sender_uid
            await assert_plaintext_allowed(db, user_uid, other_uid)
        await inspect_plaintext_write(db, payload.content, surface="messenger_plaintext" if surface == "messenger" else "space_chat", operation="edit")
        result = await edit_message(db, surface, message_uid, user_uid, payload.content)
        await _publish_frame(surface, message, _standard_frame(surface, message, overrides=result))
        return {"status": "ok", "message": result}

    @router.delete("/{surface}/{message_uid}")
    async def delete_message(surface: str, message_uid: UUID, current_user: dict = Depends(auth_middle), db: AsyncSession = Depends(Database.session_generator)):
        user_uid = _user_uid(current_user)
        message = await load_message(db, surface, message_uid)
        result = await soft_delete_message(db, surface, message_uid, user_uid)
        await _publish_frame(surface, message, _standard_frame(surface, message, overrides=result))
        return {"status": "ok", "message": result}

    @router.post("/{surface}/{message_uid}/reply", status_code=status.HTTP_201_CREATED)
    async def reply_message(surface: str, message_uid: UUID, payload: ReplyMessageRequest, current_user: dict = Depends(auth_middle), db: AsyncSession = Depends(Database.session_generator)):
        user_uid = _user_uid(current_user)
        source = await load_message(db, surface, message_uid)
        await ensure_message_access(db, surface, source, user_uid)
        if source.content_type == "deleted":
            raise HTTPException(status_code=409, detail={"error_type": "message_deleted"})
        if surface == "messenger" and source.content_type == "e2ee":
            raise HTTPException(status_code=409, detail={"error_type": "encrypted_message_reply_requires_e2ee"})
        clean = payload.content.strip()
        metadata = {"reply_to": _reply_snapshot(surface, source)}
        if surface == "room":
            await assert_allowed(db, user_uid, "space.chat.send")
            if not await active_room_member(db, source.room_uid, user_uid):
                raise HTTPException(status_code=403, detail={"error_type": "space_access_required"})
            await inspect_plaintext_write(db, clean, surface="space_chat", operation="reply")
            room_uid = source.room_uid
            created = await Message.create_message(db, {
                "content": clean,
                "content_type": "text",
                "media_metadata": metadata,
                "room_uid": str(room_uid),
                "sender_uid": str(user_uid),
                # Required for durable Space reply notification claim and
                # same-room parent verification, not only UI quote metadata.
                "reply_to_uid": str(source.uid),
                "frontId": payload.frontId,
            })
            if not created.pop("_replayed", False):
                await _publish_space_reply_after_commit(
                    db, room_uid=room_uid, sender_uid=user_uid, created=created,
                )
        elif surface == "messenger":
            await assert_allowed(db, user_uid, "messenger.send")
            target_uid = source.receiver_uid if source.sender_uid == user_uid else source.sender_uid
            if not await _dm_allowed(db, user_uid, target_uid):
                raise HTTPException(status_code=403, detail={"error_type": "dm_not_allowed"})
            await assert_plaintext_allowed(db, user_uid, target_uid)
            await inspect_plaintext_write(db, clean, surface="messenger_plaintext", operation="reply")
            created = await PrivateMessage.create_private_message(db, {"content": clean, "content_type": "text", "media_metadata": metadata, "sender_uid": str(user_uid), "receiver_uid": str(target_uid), "frontId": payload.frontId})
            if not created.pop("_replayed", False):
                try:
                    await private_manager.send_to_user(user_uid, created)
                    if target_uid != user_uid:
                        await private_manager.send_to_user(target_uid, created)
                except Exception:
                    logger.exception("DM reply saved but realtime delivery failed")
        else:
            raise HTTPException(status_code=404, detail={"error_type": "message_surface_not_found"})
        return {"status": "ok", "message": created}

    @router.get("/{surface}/{message_uid}/reactions")
    async def get_reactions(surface: str, message_uid: UUID, current_user: dict = Depends(auth_middle), db: AsyncSession = Depends(Database.session_generator)):
        user_uid = _user_uid(current_user)
        message = await load_message(db, surface, message_uid)
        await ensure_message_access(db, surface, message, user_uid)
        return {"status": "ok", "reactions": await reaction_projection(db, surface, message.uid, user_uid)}

    @router.post("/{surface}/{message_uid}/reactions")
    async def react_message(surface: str, message_uid: UUID, payload: ReactionRequest, current_user: dict = Depends(auth_middle), db: AsyncSession = Depends(Database.session_generator)):
        user_uid = _user_uid(current_user)
        message = await load_message(db, surface, message_uid)
        result = await toggle_reaction(db, surface, message_uid, user_uid, payload.emoji)
        metadata = dict(message.media_metadata or {})
        metadata["reactions"] = result["reactions"]
        await _publish_frame(surface, message, _standard_frame(surface, message, overrides={"media_metadata": metadata}))
        return {"status": "ok", **result}

    @router.post("/{surface}/{message_uid}/forward", status_code=status.HTTP_201_CREATED)
    async def forward_message(surface: str, message_uid: UUID, payload: ForwardMessageRequest, current_user: dict = Depends(auth_middle), db: AsyncSession = Depends(Database.session_generator)):
        user_uid = _user_uid(current_user)
        source = await load_message(db, surface, message_uid)
        await ensure_message_access(db, surface, source, user_uid)
        if source.content_type == "deleted":
            raise HTTPException(status_code=409, detail={"error_type": "message_deleted"})
        if source.content_type == "e2ee":
            # An encrypted envelope must never be forwarded as plaintext or as an
            # undecryptable "e2ee" row without the corresponding device envelopes.
            raise HTTPException(status_code=409, detail={"error_type": "encrypted_message_forward_requires_e2ee"})
        metadata = dict(source.media_metadata or {})
        metadata["forwarded_from"] = {"surface": surface, "message_uid": str(source.uid), "author_uid": str(source.author_uid if surface == "room" else source.sender_uid)}
        if payload.target_surface == "room":
            await assert_allowed(db, user_uid, "space.chat.send")
            if not await active_room_member(db, payload.target_uid, user_uid):
                raise HTTPException(status_code=403, detail={"error_type": "space_access_required"})
            await inspect_plaintext_write(db, source.text or "", surface="space_chat", operation="forward")
            forwarded = await Message.create_message(db, {"content": source.text, "content_type": source.content_type, "media_metadata": metadata, "room_uid": str(payload.target_uid), "sender_uid": str(user_uid)})
            await room_manager.broadcast_to_room(payload.target_uid, forwarded)
        elif payload.target_surface == "messenger":
            await assert_allowed(db, user_uid, "messenger.send")
            if not await _dm_allowed(db, user_uid, payload.target_uid):
                raise HTTPException(status_code=403, detail={"error_type": "dm_not_allowed"})
            await assert_plaintext_allowed(db, user_uid, payload.target_uid)
            await inspect_plaintext_write(db, source.text or "", surface="messenger_plaintext", operation="forward")
            forwarded = await PrivateMessage.create_private_message(db, {"content": source.text, "content_type": source.content_type, "media_metadata": metadata, "sender_uid": str(user_uid), "receiver_uid": str(payload.target_uid)})
            await private_manager.send_to_user(user_uid, forwarded)
            if payload.target_uid != user_uid:
                await private_manager.send_to_user(payload.target_uid, forwarded)
        else:
            raise HTTPException(status_code=422, detail={"error_type": "invalid_target_surface"})
        return {"status": "ok", "message": forwarded}

    app.include_router(router)
