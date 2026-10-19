from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from components.discovery.service import DISCOVERY_POOL_LIMIT, discover_spaces
from components.moderation.model import PlatformRestriction


async def discover_spaces_with_moderation(
    db: AsyncSession,
    viewer_uid: UUID | str,
    *,
    query: str | None = None,
    purpose: str | None = None,
    tag: str | None = None,
    category: str | None = None,
    limit: int = 30,
    offset: int = 0,
) -> list[dict]:
    """Apply Account-level organic-discovery restrictions before pagination.

    Existing owner/member relationships are not hidden by a discovery sanction;
    the restriction only prevents the affected Account from being published to
    unrelated users through the organic discovery surface.
    """
    viewer = UUID(str(viewer_uid))
    ranked = await discover_spaces(
        db,
        viewer_uid=viewer,
        query=query,
        purpose=purpose,
        tag=tag,
        category=category,
        limit=DISCOVERY_POOL_LIMIT,
        offset=0,
    )
    if not ranked:
        return []

    owner_uids: set[UUID] = set()
    for space in ranked:
        owner_uid = space.get("owner_uid")
        if not owner_uid:
            continue
        try:
            owner_uids.add(UUID(str(owner_uid)))
        except (TypeError, ValueError):
            continue

    now = datetime.utcnow()
    restricted_owner_uids: set[UUID] = set()
    if owner_uids:
        result = await db.execute(
            select(PlatformRestriction.target_account_uid)
            .where(
                PlatformRestriction.target_account_uid.in_(owner_uids),
                PlatformRestriction.status == "active",
                PlatformRestriction.starts_at <= now,
                or_(
                    PlatformRestriction.expires_at.is_(None),
                    PlatformRestriction.expires_at > now,
                ),
                PlatformRestriction.capability.in_(["discovery.publish", "account.access"]),
                PlatformRestriction.scope_type == "platform",
            )
            .distinct()
        )
        restricted_owner_uids = set(result.scalars().all())

    eligible: list[dict] = []
    for space in ranked:
        owner_uid = space.get("owner_uid")
        try:
            owner_account_uid = UUID(str(owner_uid)) if owner_uid else None
        except (TypeError, ValueError):
            owner_account_uid = None
        membership_status = (space.get("viewer_membership") or {}).get("status")
        is_owner = owner_account_uid == viewer

        if (
            owner_account_uid in restricted_owner_uids
            and not is_owner
            and membership_status not in {"active", "pending"}
        ):
            continue
        eligible.append(space)

    return eligible[offset : offset + limit]
