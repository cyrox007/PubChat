from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from components.auth.middleware import auth_middle
from components.space.live_state import get_spaces_live_state
from components.space.pulse import get_space_pulse
from database import Database


class SpaceLiveStateRequest(BaseModel):
    space_uids: list[UUID] = Field(default_factory=list, max_length=50)


def install(app: FastAPI) -> None:
    router = APIRouter(prefix="/spaces/v1", tags=["spaces-v1"])

    @router.post("/live-state")
    async def live_state(
        payload: SpaceLiveStateRequest,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        live = await get_spaces_live_state(
            db,
            viewer_uid=current_user["user_uid"],
            space_uids=payload.space_uids,
        )
        return {"status": "ok", **live}

    @router.get("/{space_uid}/pulse")
    async def pulse(
        space_uid: UUID,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        item = await get_space_pulse(
            db,
            space_uid=space_uid,
            viewer_uid=current_user["user_uid"],
        )
        return {"status": "ok", "pulse": item}

    app.include_router(router)
