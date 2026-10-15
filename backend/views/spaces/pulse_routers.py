from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from components.auth.middleware import auth_middle
from components.space.pulse import get_space_pulse
from database import Database


def install(app: FastAPI) -> None:
    router = APIRouter(prefix="/spaces/v1", tags=["spaces-v1"])

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
