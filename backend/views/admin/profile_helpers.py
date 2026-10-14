from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from components.identity.model import Account, Persona
from components.message.model import Message, PrivateMessage
from components.room.model import Room, RoomMember
from components.user.model import Penalty, User


async def build_admin_user_projection(db: AsyncSession, user: User) -> dict:
    account_result = await db.execute(
        select(Account).where(
            or_(Account.legacy_user_uid == user.uid, Account.uid == user.uid)
        ).limit(1)
    )
    account = account_result.scalar_one_or_none()

    persona = None
    if account:
        persona_result = await db.execute(
            select(Persona).where(
                Persona.account_uid == account.uid,
                Persona.is_primary.is_(True),
            ).limit(1)
        )
        persona = persona_result.scalar_one_or_none()

    rooms_owned = int((await db.execute(
        select(func.count(Room.uid)).where(Room.owner_uid == user.uid, Room.is_active.is_(True))
    )).scalar_one() or 0)
    rooms_joined = int((await db.execute(
        select(func.count(RoomMember.id)).where(RoomMember.user_uid == user.uid, RoomMember.is_banned.is_(False))
    )).scalar_one() or 0)
    messages_count = int((await db.execute(
        select(func.count(Message.uid)).where(Message.author_uid == user.uid)
    )).scalar_one() or 0)
    dm_sent_count = int((await db.execute(
        select(func.count(PrivateMessage.id)).where(PrivateMessage.sender_uid == user.uid)
    )).scalar_one() or 0)
    penalties_count = int((await db.execute(
        select(func.count(Penalty.id)).where(Penalty.user_uid == user.uid)
    )).scalar_one() or 0)

    return {
        "uid": str(user.uid),
        "username": user.username,
        "email": user.email,
        "phone": user.phone,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "avatar": user.avatar,
        "global_role": user.global_role,
        "rating": user.rating,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_online": user.last_online.isoformat() if user.last_online else None,
        "is_active": bool(user.is_active),
        "is_verified": bool(user.is_verified),
        "deleted_at": user.deleted_at.isoformat() if user.deleted_at else None,
        "city": user.city,
        "country": user.country,
        "bio": user.bio,
        "date_of_birth": user.date_of_birth.isoformat() if user.date_of_birth else None,
        "gender": user.gender,
        "career": user.career,
        "education": user.education,
        "marital_status": user.marital_status,
        "account": {
            "uid": str(account.uid),
            "status": account.status,
            "trust_level": account.trust_level,
            "created_at": account.created_at.isoformat() if account.created_at else None,
        } if account else None,
        "persona": {
            "uid": str(persona.uid),
            "handle": persona.handle,
            "display_name": persona.display_name,
            "social_intent": persona.social_intent,
        } if persona else None,
        "stats": {
            "rooms_owned": rooms_owned,
            "rooms_joined": rooms_joined,
            "messages": messages_count,
            "dm_sent": dm_sent_count,
            "penalties": penalties_count,
        },
    }
