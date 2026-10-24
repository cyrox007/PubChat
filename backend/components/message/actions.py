from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from components.message.model import Message, PrivateMessage
from components.message.reaction_model import MessageReaction
from components.identity.model import Account
from components.room.model import RoomBan, RoomMember
from components.space.model import SpaceMembership


SURFACES = {"room": Message, "messenger": PrivateMessage}


def _model(surface: str):
    model = SURFACES.get(surface)
    if not model:
        raise HTTPException(status_code=404, detail={"error_type": "message_surface_not_found"})
    return model


async def load_message(db: AsyncSession, surface: str, message_uid: UUID | str):
    try:
        uid = UUID(str(message_uid))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=404, detail={"error_type": "message_not_found"}) from exc
    message = await db.get(_model(surface), uid)
    if not message:
        raise HTTPException(status_code=404, detail={"error_type": "message_not_found"})
    return message


def author_uid(surface: str, message) -> UUID:
    return message.author_uid if surface == "room" else message.sender_uid


async def active_room_member(db: AsyncSession, room_uid: UUID, user_uid: UUID) -> bool:
    """Use authoritative Account/Space membership for linked Identity v2 users.

    An old room_members entry must not override a removed modern membership.
    Only unmigrated legacy users fall back to the legacy membership table.
    """
    if await RoomBan.is_user_banned(db, room_uid, user_uid):
        return False
    account = (
        await db.execute(
            select(Account).where(Account.legacy_user_uid == user_uid).limit(1)
        )
    ).scalar_one_or_none()
    if account is not None:
        if account.status != "active" or account.deleted_at is not None:
            return False
        membership = (
            await db.execute(
                select(SpaceMembership.uid).where(
                    SpaceMembership.room_uid == room_uid,
                    SpaceMembership.account_uid == account.uid,
                    SpaceMembership.status == "active",
                ).limit(1)
            )
        ).scalar_one_or_none()
        return membership is not None
    legacy_member = (
        await db.execute(
            select(RoomMember.id).where(
                RoomMember.room_uid == room_uid,
                RoomMember.user_uid == user_uid,
                RoomMember.is_banned.is_(False),
            ).limit(1)
        )
    ).scalar_one_or_none()
    return legacy_member is not None


async def ensure_message_access(db: AsyncSession, surface: str, message, user_uid: UUID, *, write: bool = False) -> None:
    if write and author_uid(surface, message) != user_uid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error_type": "message_author_required"})
    if surface == "messenger":
        if user_uid not in {message.sender_uid, message.receiver_uid}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error_type": "message_access_denied"})
        return
    if message.author_uid == user_uid:
        return
    if not await active_room_member(db, message.room_uid, user_uid):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error_type": "message_access_denied"})


def _metadata(message) -> dict:
    return dict(message.media_metadata or {})


async def edit_message(db: AsyncSession, surface: str, message_uid: UUID | str, user_uid: UUID, text: str) -> dict:
    message = await load_message(db, surface, message_uid)
    await ensure_message_access(db, surface, message, user_uid, write=True)
    if message.content_type == "deleted":
        raise HTTPException(status_code=409, detail={"error_type": "message_deleted"})
    clean = text.strip()
    if not clean or len(clean) > 1000:
        raise HTTPException(status_code=422, detail={"error_type": "invalid_message_text"})
    message.text = clean
    metadata = _metadata(message)
    edited_at = datetime.utcnow().isoformat()
    metadata["edited_at"] = edited_at
    message.media_metadata = metadata
    await db.commit()
    return {"uid": str(message.uid), "surface": surface, "content": clean, "content_type": message.content_type, "media_metadata": metadata, "edited_at": edited_at}


async def soft_delete_message(db: AsyncSession, surface: str, message_uid: UUID | str, user_uid: UUID) -> dict:
    message = await load_message(db, surface, message_uid)
    await ensure_message_access(db, surface, message, user_uid, write=True)
    deleted_at = datetime.utcnow().isoformat()
    # Public message history keeps the position/replies intact while removing user content.
    message.text = None
    message.content_type = "deleted"
    message.media_metadata = {"deleted_at": deleted_at}
    await db.execute(delete(MessageReaction).where(MessageReaction.surface == surface, MessageReaction.message_uid == message.uid))
    await db.commit()
    return {"uid": str(message.uid), "surface": surface, "content": "", "content_type": "deleted", "media_metadata": message.media_metadata, "deleted_at": deleted_at}


async def toggle_reaction(db: AsyncSession, surface: str, message_uid: UUID | str, user_uid: UUID, emoji: str) -> dict:
    message = await load_message(db, surface, message_uid)
    await ensure_message_access(db, surface, message, user_uid)
    value = emoji.strip()
    if not value or len(value) > 32:
        raise HTTPException(status_code=422, detail={"error_type": "invalid_reaction"})
    existing = (
        await db.execute(
            select(MessageReaction).where(
                MessageReaction.surface == surface,
                MessageReaction.message_uid == message.uid,
                MessageReaction.user_uid == user_uid,
                MessageReaction.emoji == value,
            )
        )
    ).scalar_one_or_none()
    if existing:
        await db.delete(existing)
        selected = False
    else:
        db.add(MessageReaction(surface=surface, message_uid=message.uid, user_uid=user_uid, emoji=value))
        selected = True
    await db.commit()
    return {"selected": selected, "reactions": await reaction_projection(db, surface, message.uid, user_uid)}


async def reaction_projection(db: AsyncSession, surface: str, message_uid: UUID, viewer_uid: UUID | None = None) -> list[dict]:
    rows = (
        await db.execute(
            select(MessageReaction).where(
                MessageReaction.surface == surface,
                MessageReaction.message_uid == message_uid,
            ).order_by(MessageReaction.created_at.asc())
        )
    ).scalars().all()
    grouped: dict[str, list[UUID]] = defaultdict(list)
    for row in rows:
        grouped[row.emoji].append(row.user_uid)
    return [
        {
            "emoji": emoji,
            "count": len(users),
            "selected": bool(viewer_uid and viewer_uid in users),
        }
        for emoji, users in grouped.items()
    ]
