from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlalchemy.ext.asyncio import AsyncSession

from components.auth.middleware import auth_middle
from components.discovery.moderation import discover_spaces_with_moderation
from components.discovery.service import DISCOVERY_ALGORITHM
from components.space.live_state import get_spaces_live_state
from components.space.schemas import SpacePurpose
from database import Database


def _attach_live_state(items: list[dict], live_payload: dict) -> list[dict]:
    live_by_uid = {
        item["space_uid"]: item
        for item in live_payload.get("spaces", [])
    }
    for space in items:
        live = live_by_uid.get(str(space.get("uid")))
        if not live:
            continue
        discovery = space.setdefault("discovery", {})
        discovery["live"] = live
        reasons = discovery.setdefault("reasons", [])
        existing_codes = {reason.get("code") for reason in reasons}

        present_count = live.get("present_count")
        if present_count and "live_presence" not in existing_codes:
            reasons.insert(
                0,
                {
                    "code": "live_presence",
                    "label": f"{present_count} сейчас здесь",
                },
            )
        if live.get("conversation", {}).get("active") and "live_conversation" not in existing_codes:
            reasons.insert(
                0,
                {
                    "code": "live_conversation",
                    "label": "Разговор идёт сейчас",
                },
            )
    return items


def install(app: FastAPI) -> None:
    router = APIRouter(prefix="/discovery/v1", tags=["discovery-v1"])

    @router.get("/spaces")
    async def spaces(
        q: Optional[str] = Query(default=None, max_length=80),
        purpose: Optional[SpacePurpose] = None,
        tag: Optional[str] = Query(default=None, max_length=40),
        limit: int = Query(default=30, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=150),
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        items = await discover_spaces_with_moderation(
            db,
            viewer_uid=current_user["user_uid"],
            query=q,
            purpose=purpose,
            tag=tag,
            limit=limit,
            offset=offset,
        )
        live_payload = await get_spaces_live_state(
            db,
            viewer_uid=current_user["user_uid"],
            space_uids=[UUID(str(item["uid"])) for item in items if item.get("uid")],
        )
        _attach_live_state(items, live_payload)
        return {
            "status": "ok",
            "algorithm": DISCOVERY_ALGORITHM,
            "spaces": items,
            "live_generated_at": live_payload.get("generated_at"),
            "live_presence_available": live_payload.get("presence_available", False),
            "pagination": {
                "limit": limit,
                "offset": offset,
                "count": len(items),
            },
        }

    app.include_router(router)
