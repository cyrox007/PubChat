from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from components.auth.middleware import auth_middle
from components.identity.model import Account
from components.realtime import RealtimeUnavailable, realtime_service
from components.realtime.schemas import RealtimeTicketRequest
from components.room.model import Room, RoomBan
from components.space.model import SpaceMembership
from database import Database


def install(app: FastAPI) -> None:
    router = APIRouter(prefix="/realtime/v2", tags=["realtime-v2"])

    @router.post("/tickets", status_code=status.HTTP_201_CREATED)
    async def create_ticket(
        payload: RealtimeTicketRequest,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        account_uid = current_user["user_uid"]
        resource_uid = None

        if payload.target == "room":
            room = await Room.get_room_by_uid(db, payload.room_uid)
            if not room or not room.is_active:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error_type": "room_not_found"},
                )

            normalized_account_uid = UUID(str(account_uid))
            account = await db.get(Account, normalized_account_uid)
            legacy_user_uid = (
                account.legacy_user_uid
                if account and account.legacy_user_uid
                else normalized_account_uid
            )

            if await RoomBan.is_user_banned(db, payload.room_uid, legacy_user_uid):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"error_type": "space_access_denied"},
                )

            membership_result = await db.execute(
                select(SpaceMembership.uid).where(
                    SpaceMembership.room_uid == payload.room_uid,
                    SpaceMembership.account_uid == normalized_account_uid,
                    SpaceMembership.status == "active",
                ).limit(1)
            )
            has_active_membership = membership_result.scalar_one_or_none() is not None
            is_owner = room.owner_uid == legacy_user_uid
            if not is_owner and not has_active_membership:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"error_type": "space_membership_required"},
                )

            resource_uid = payload.room_uid

        try:
            ticket, expires_in = await realtime_service.issue_ticket(
                account_uid=account_uid,
                target=payload.target,
                resource_uid=resource_uid,
                session_uid=current_user.get("session_uid"),
                device_uid=current_user.get("device_uid"),
            )
        except RealtimeUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"error_type": "realtime_unavailable"},
            ) from exc

        websocket_path = (
            f"/ws/v2/rooms/{payload.room_uid}"
            if payload.target == "room"
            else "/ws/v2/messenger"
        )
        return {
            "status": "ok",
            "protocol": 2,
            "ticket": ticket,
            "expires_in": expires_in,
            "websocket_path": websocket_path,
        }

    app.include_router(router)
