"""Server-owned Space taxonomy and administrator audit log."""
import json
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from components.space.category_model import SpaceCategory, SpaceCategoryAssignment, SpaceCategoryAudit
from components.space.category_schemas import CategoryCreate, CategoryUpdate

def project_category(category: SpaceCategory) -> dict:
    return {
        "slug": category.slug,
        "name": category.name,
        "icon": category.icon,
        "description": category.description,
        "locale": category.locale,
        "position": category.position,
        "is_active": category.is_active,
    }

async def list_categories(db: AsyncSession, *, include_inactive: bool = False) -> list[dict]:
    stmt = select(SpaceCategory)
    if not include_inactive:
        stmt = stmt.where(SpaceCategory.is_active.is_(True))
    result = await db.execute(stmt.order_by(SpaceCategory.position, SpaceCategory.slug))
    return [project_category(item) for item in result.scalars().all()]

async def validate_categories(db: AsyncSession, slugs: list[str]) -> None:
    if not slugs:
        return
    found = await db.execute(select(SpaceCategory.slug).where(
        SpaceCategory.slug.in_(slugs), SpaceCategory.is_active.is_(True)
    ))
    if set(found.scalars().all()) != set(slugs):
        raise HTTPException(status_code=422, detail={"error_type": "invalid_or_inactive_space_category"})

async def replace_space_categories(db: AsyncSession, room_uid: UUID, slugs: list[str]) -> None:
    # Caller owns the transaction and MUST have checked ownership/creation.
    await validate_categories(db, slugs)
    await db.execute(delete(SpaceCategoryAssignment).where(SpaceCategoryAssignment.room_uid == room_uid))
    for slug in slugs:
        db.add(SpaceCategoryAssignment(room_uid=room_uid, category_slug=slug))

def _write_audit(db: AsyncSession, slug: str, actor_uid: UUID, action: str, changes: dict) -> None:
    db.add(SpaceCategoryAudit(
        category_slug=slug,
        actor_account_uid=actor_uid,
        action=action,
        change_summary=json.dumps(changes, ensure_ascii=False, sort_keys=True),
    ))

async def create_category(db: AsyncSession, actor_uid: UUID, payload: CategoryCreate) -> dict:
    if await db.get(SpaceCategory, payload.slug):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error_type": "category_slug_taken"})
    data = payload.model_dump()
    item = SpaceCategory(**data)
    if not item.is_active:
        item.archived_at = datetime.utcnow()
    db.add(item)
    _write_audit(db, item.slug, actor_uid, "create", data)
    await db.commit()
    return project_category(item)

async def update_category(
    db: AsyncSession, actor_uid: UUID, slug: str, payload: CategoryUpdate,
) -> dict:
    item = await db.get(SpaceCategory, slug)
    if not item:
        raise HTTPException(status_code=404, detail={"error_type": "space_category_not_found"})
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return project_category(item)
    for key, value in changes.items():
        if key != "description" and value is None:
            raise HTTPException(status_code=422, detail={"error_type": "invalid_category_field"})
        setattr(item, key, value)
    if "is_active" in changes:
        item.archived_at = None if item.is_active else datetime.utcnow()
    item.updated_at = datetime.utcnow()
    _write_audit(db, slug, actor_uid, "update", changes)
    await db.commit()
    return project_category(item)

async def list_category_audit(db: AsyncSession, *, limit: int = 50) -> list[dict]:
    result = await db.execute(select(SpaceCategoryAudit)
        .order_by(SpaceCategoryAudit.created_at.desc(), SpaceCategoryAudit.uid.desc())
        .limit(limit))
    return [{
        "uid": str(row.uid),
        "category_slug": row.category_slug,
        "actor_account_uid": str(row.actor_account_uid) if row.actor_account_uid else None,
        "action": row.action,
        "changes": json.loads(row.change_summary),
        "created_at": row.created_at.isoformat(),
    } for row in result.scalars().all()]
