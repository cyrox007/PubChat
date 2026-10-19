"""Public category catalog and platform-admin taxonomy management."""
from fastapi import APIRouter, Depends, FastAPI, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from components.auth.middleware import auth_middle
from components.auth.permissions import require_admin
from components.space.category_schemas import CategoryCreate, CategoryUpdate
from components.space.category_service import (
    create_category, list_categories, list_category_audit, update_category,
)
from database import Database


def install(app: FastAPI) -> None:
    public = APIRouter(prefix="/spaces/v1", tags=["space-categories"])

    @public.get("/categories")
    async def active_categories(
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        # Anonymous enumeration is unnecessary; this is the authenticated
        # catalog used by Web, Android, and iOS.
        return {"status": "ok", "categories": await list_categories(db)}

    app.include_router(public)

    admin = APIRouter(
        prefix="/admin/space-categories", tags=["admin-space-categories"],
        dependencies=[Depends(require_admin)],
    )

    @admin.get("")
    async def index(db: AsyncSession = Depends(Database.session_generator)):
        return {"status": "ok", "categories": await list_categories(db, include_inactive=True)}

    @admin.get("/audit")
    async def audit(
        limit: int = Query(default=50, ge=1, le=100),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        return {"status": "ok", "events": await list_category_audit(db, limit=limit)}

    @admin.post("", status_code=status.HTTP_201_CREATED)
    async def create(
        payload: CategoryCreate,
        actor=Depends(require_admin),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        return {"status": "ok", "category": await create_category(db, actor.uid, payload)}

    @admin.patch("/{slug}")
    async def patch(
        slug: str,
        payload: CategoryUpdate,
        actor=Depends(require_admin),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        return {"status": "ok", "category": await update_category(db, actor.uid, slug, payload)}

    app.include_router(admin)
