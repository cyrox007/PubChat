from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from components.reputation.service import get_current_reputation_assessment


async def public_reputation_projection(db: AsyncSession, account_uid: UUID) -> dict:
    """Return the intentionally small reputation surface visible on profiles.

    Provider/model details, rationale, confidence and raw behavioral features are
    private. Public profiles expose qualitative reputation only, so the UI cannot
    turn the system into a gameable public points leaderboard.
    """
    item = await get_current_reputation_assessment(db, account_uid)
    if item is None:
        return {
            "status": "unassessed",
            "label": "unknown",
            "dimensions": {},
        }
    return {
        "status": "assessed",
        "label": item.overall_label,
        "dimensions": item.dimensions or {},
    }


async def self_reputation_projection(db: AsyncSession, account_uid: UUID) -> dict:
    """Return the owner-facing reputation/privilege state without model internals."""
    item = await get_current_reputation_assessment(db, account_uid)
    if item is None:
        return {
            "status": "unassessed",
            "label": "unknown",
            "dimensions": {},
            "privileges": {"space_create": False, "max_owned_active_spaces": 0},
            "valid_until": None,
        }
    return {
        "status": "assessed",
        "label": item.overall_label,
        "dimensions": item.dimensions or {},
        "privileges": {
            "space_create": bool(item.space_creation_eligible),
            "max_owned_active_spaces": int(item.max_owned_active_spaces),
        },
        "valid_until": item.valid_until.isoformat(),
    }
