from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from components.auth.permissions import require_admin
from components.user.model import User
from database import Database
from views.admin.profile_helpers import build_admin_user_projection


def install(app: FastAPI) -> None:
    router = APIRouter(
        prefix="/admin",
        tags=["admin-users"],
        dependencies=[Depends(require_admin)],
    )

    @router.get("/users/{target_uid}/overview")
    async def user_overview(
        target_uid: UUID,
        db: AsyncSession = Depends(Database.session_generator),
    ):
        user = await User.get_user_by_uid(db, target_uid)
        if not user or user.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_type": "admin_user_not_found"},
            )
        return {
            "status": "ok",
            "user": await build_admin_user_projection(db, user),
        }

    app.include_router(router)
