from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlalchemy.ext.asyncio import AsyncSession

from components.auth.middleware import auth_middle
from components.identity.schemas import SocialIntent
from components.social.availability import (
    SocialAvailabilityRequest,
    clear_social_availability,
    get_social_availability,
    set_social_availability,
)
from components.social.discovery import discover_people
from components.social.schemas import FriendActionRequest, RequestDirection
from components.social.service import (
    apply_friend_action,
    block_account,
    follow_account,
    list_friend_requests,
    list_friends,
    relationship_projection,
    unblock_account,
    unfollow_account,
)
from database import Database


def install(app: FastAPI) -> None:
    router = APIRouter(prefix="/social/v1", tags=["social-v1"])

    @router.get("/discover")
    async def discover(
        q: Optional[str] = Query(default=None, max_length=80),
        social_intent: Optional[SocialIntent] = None,
        available_now: bool = Query(default=False),
        limit: int = Query(default=30, ge=1, le=50),
        offset: int = Query(default=0, ge=0),
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        people, total = await discover_people(
            db,
            viewer_uid=current_user["user_uid"],
            query=q,
            social_intent=social_intent,
            available_now=available_now,
            limit=limit,
            offset=offset,
        )
        return {
            "status": "ok",
            "people": people,
            "pagination": {"limit": limit, "offset": offset, "count": len(people), "total": total},
        }

    @router.get("/availability/me")
    async def my_availability(
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        return {
            "status": "ok",
            "availability": await get_social_availability(db, current_user["user_uid"]),
        }

    @router.put("/availability/me")
    async def update_my_availability(
        payload: SocialAvailabilityRequest,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        availability = await set_social_availability(db, current_user["user_uid"], payload)
        return {"status": "ok", "availability": availability}

    @router.delete("/availability/me")
    async def delete_my_availability(
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        await clear_social_availability(db, current_user["user_uid"])
        return {"status": "ok", "availability": None}

    @router.get("/relationships/{account_uid}")
    async def relationship(
        account_uid: UUID,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        relation = await relationship_projection(db, current_user["user_uid"], account_uid)
        return {"status": "ok", "relationship": relation}

    @router.post("/follows/{account_uid}")
    async def follow(
        account_uid: UUID,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        relation = await follow_account(db, current_user["user_uid"], account_uid)
        return {"status": "ok", "relationship": relation}

    @router.delete("/follows/{account_uid}")
    async def unfollow(
        account_uid: UUID,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        relation = await unfollow_account(db, current_user["user_uid"], account_uid)
        return {"status": "ok", "relationship": relation}

    @router.patch("/friends/{account_uid}")
    async def friend_action(
        account_uid: UUID,
        payload: FriendActionRequest,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        relation = await apply_friend_action(
            db,
            current_user["user_uid"],
            account_uid,
            payload.action,
        )
        return {"status": "ok", "relationship": relation}

    @router.get("/friends")
    async def friends(
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        items, total = await list_friends(db, current_user["user_uid"], limit, offset)
        return {
            "status": "ok",
            "friends": items,
            "pagination": {"limit": limit, "offset": offset, "count": len(items), "total": total},
        }

    @router.get("/friend-requests")
    async def friend_requests(
        direction: RequestDirection = Query(default="incoming"),
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        items, total = await list_friend_requests(
            db,
            current_user["user_uid"],
            direction,
            limit,
            offset,
        )
        return {
            "status": "ok",
            "requests": items,
            "direction": direction,
            "pagination": {"limit": limit, "offset": offset, "count": len(items), "total": total},
        }

    @router.post("/blocks/{account_uid}")
    async def block(
        account_uid: UUID,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        relation = await block_account(db, current_user["user_uid"], account_uid)
        return {"status": "ok", "relationship": relation}

    @router.delete("/blocks/{account_uid}")
    async def unblock(
        account_uid: UUID,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        relation = await unblock_account(db, current_user["user_uid"], account_uid)
        return {"status": "ok", "relationship": relation}

    app.include_router(router)
