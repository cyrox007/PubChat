from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, Query
from sqlalchemy.ext.asyncio import AsyncSession

from components.auth.middleware import auth_middle
from components.discovery.moderation import discover_spaces_with_moderation
from components.discovery.service import DISCOVERY_ALGORITHM, DISCOVERY_POOL_LIMIT
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


def _live_now_items(items: list[dict]) -> list[dict]:
    """Return only currently-live Spaces using an explicit, inspectable order.

    This mode is opt-in and does not alter the default organic ranking. Active
    conversations come first, then actual room presence, then the number of
    distinct recent contributors. Python's stable sort preserves the existing
    organic order when all live signals are equal.
    """

    live_items = [
        item
        for item in items
        if (item.get("discovery") or {}).get("live", {}).get("live")
    ]

    def sort_key(item: dict) -> tuple[int, int, int]:
        live = (item.get("discovery") or {}).get("live") or {}
        conversation = live.get("conversation") or {}
        return (
            -int(bool(conversation.get("active"))),
            -int(live.get("present_count") or 0),
            -int(conversation.get("contributor_count") or 0),
        )

    return sorted(live_items, key=sort_key)


def install(app: FastAPI) -> None:
    router = APIRouter(prefix="/discovery/v1", tags=["discovery-v1"])

    @router.get("/spaces")
    async def spaces(
        q: Optional[str] = Query(default=None, max_length=80),
        purpose: Optional[SpacePurpose] = None,
        tag: Optional[str] = Query(default=None, max_length=40),
        live_now: bool = Query(default=False),
        limit: int = Query(default=30, ge=1, le=50),
        offset: int = Query(default=0, ge=0, le=150),
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        pool_limit = DISCOVERY_POOL_LIMIT if live_now else limit
        pool_offset = 0 if live_now else offset
        items = await discover_spaces_with_moderation(
            db,
            viewer_uid=current_user["user_uid"],
            query=q,
            purpose=purpose,
            tag=tag,
            limit=pool_limit,
            offset=pool_offset,
        )
        live_payload = await get_spaces_live_state(
            db,
            viewer_uid=current_user["user_uid"],
            space_uids=[UUID(str(item["uid"])) for item in items if item.get("uid")],
            max_spaces=DISCOVERY_POOL_LIMIT if live_now else 50,
        )
        _attach_live_state(items, live_payload)

        if live_now:
            items = _live_now_items(items)[offset : offset + limit]

        return {
            "status": "ok",
            "algorithm": DISCOVERY_ALGORITHM,
            "mode": "live_now" if live_now else "organic",
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
