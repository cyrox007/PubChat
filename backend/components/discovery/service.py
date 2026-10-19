from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from components.engagement.model import SpaceActivity
from components.engagement.occurrence_model import ActivityOccurrence
from components.identity.model import AccountRelationship, Persona
from components.message.model import Message
from components.room.model import Room
from components.space.model import SpaceEvent, SpaceMembership, SpaceSettings, SpaceTag
from components.space.service import list_spaces


DISCOVERY_POOL_LIMIT = 200
DISCOVERY_SOURCE_LIMIT = 64
DISCOVERY_ALGORITHM = "organic-v2"
UPCOMING_WINDOW_DAYS = 14
RECENT_ACTIVITY_HOURS = 24

INTENT_PURPOSES = {
    "open": {"conversation", "community"},
    "meet": {"meet_people"},
    "games": {"games"},
}

REASON_LABELS = {
    "already_member": "Вы уже участник",
    "request_pending": "Ваша заявка уже рассматривается",
    "active_conversation": "Здесь недавно общались",
    "upcoming_activity": "Скоро общая активность",
    "shared_topics": "Похожие темы на ваши пространства",
    "familiar_format": "Знакомый вам формат",
    "intent_match": "Подходит вашему текущему настрою",
    "new_space": "Новое пространство",
}


def _reason(code: str) -> dict:
    return {"code": code, "label": REASON_LABELS[code]}


def _normalize_topic(value: str) -> str:
    return " ".join(str(value).split()).strip().casefold()


def _parse_created_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


async def _blocked_account_uids(db: AsyncSession, viewer_uid: UUID) -> set[UUID]:
    result = await db.execute(
        select(
            AccountRelationship.from_account_uid,
            AccountRelationship.to_account_uid,
        ).where(
            AccountRelationship.relation_type == "block",
            or_(
                AccountRelationship.from_account_uid == viewer_uid,
                AccountRelationship.to_account_uid == viewer_uid,
            ),
        )
    )
    blocked: set[UUID] = set()
    for from_uid, to_uid in result.all():
        blocked.add(to_uid if from_uid == viewer_uid else from_uid)
    blocked.discard(viewer_uid)
    return blocked


async def _viewer_context(
    db: AsyncSession,
    viewer_uid: UUID,
) -> tuple[set[str], set[str], set[str], str | None]:
    membership_result = await db.execute(
        select(SpaceMembership.room_uid).where(
            SpaceMembership.account_uid == viewer_uid,
            SpaceMembership.status == "active",
        )
    )
    room_uids = [room_uid for (room_uid,) in membership_result.all()]

    purposes: set[str] = set()
    tags: set[str] = set()
    tag_slugs: set[str] = set()
    if room_uids:
        purpose_result = await db.execute(
            select(SpaceSettings.purpose).where(SpaceSettings.room_uid.in_(room_uids))
        )
        purposes = {str(purpose) for (purpose,) in purpose_result.all() if purpose}

        tag_result = await db.execute(
            select(SpaceTag.label, SpaceTag.slug).where(SpaceTag.room_uid.in_(room_uids))
        )
        tag_rows = tag_result.all()
        tags = {
            _normalize_topic(label)
            for label, _ in tag_rows
            if label and _normalize_topic(label)
        }
        tag_slugs = {
            str(slug)
            for _, slug in tag_rows
            if slug
        }

    persona_result = await db.execute(
        select(Persona.social_intent)
        .where(Persona.account_uid == viewer_uid, Persona.is_primary.is_(True))
        .limit(1)
    )
    social_intent = persona_result.scalar_one_or_none()
    return purposes, tags, tag_slugs, str(social_intent) if social_intent else None


def _round_robin_unique(
    sources: list[list[UUID]],
    *,
    limit: int,
) -> list[UUID]:
    """Interleave bounded candidate sources without letting one source dominate."""
    if limit <= 0:
        return []

    iterators = [iter(source) for source in sources if source]
    seen: set[UUID] = set()
    result: list[UUID] = []

    while iterators and len(result) < limit:
        next_round = []
        for iterator in iterators:
            try:
                value = next(iterator)
            except StopIteration:
                continue
            next_round.append(iterator)
            if value in seen:
                continue
            seen.add(value)
            result.append(value)
            if len(result) >= limit:
                break
        iterators = next_round

    return result


async def _candidate_room_uids(
    db: AsyncSession,
    viewer_uid: UUID,
    *,
    viewer_purposes: set[str],
    viewer_tags: set[str],
    viewer_tag_slugs: set[str],
    now: datetime,
) -> list[UUID]:
    """Build an internal bounded candidate pool from independent organic sources.

    Candidate generation never grants visibility. Every UID is passed through
    canonical Space eligibility afterwards, before any ranking metadata is read
    or returned to the client.
    """
    membership_result = await db.execute(
        select(SpaceMembership.room_uid)
        .where(
            SpaceMembership.account_uid == viewer_uid,
            SpaceMembership.status.in_(["active", "pending"]),
        )
        .order_by(
            SpaceMembership.updated_at.desc(),
            SpaceMembership.joined_at.desc(),
        )
        .limit(DISCOVERY_SOURCE_LIMIT)
    )
    membership_uids = [room_uid for (room_uid,) in membership_result.all()]

    recent_since = now - timedelta(hours=RECENT_ACTIVITY_HOURS)
    recent_count = func.count(func.distinct(Message.author_uid))
    recent_latest = func.max(Message.created_at)
    recent_result = await db.execute(
        select(Message.room_uid, recent_count, recent_latest)
        .where(
            Message.room_uid.is_not(None),
            Message.author_uid.is_not(None),
            Message.created_at >= recent_since,
        )
        .group_by(Message.room_uid)
        .order_by(recent_count.desc(), recent_latest.desc())
        .limit(DISCOVERY_SOURCE_LIMIT)
    )
    recent_uids = [room_uid for room_uid, _, _ in recent_result.all() if room_uid]

    upcoming_until = now + timedelta(days=UPCOMING_WINDOW_DAYS)
    next_event = func.min(SpaceEvent.starts_at)
    event_result = await db.execute(
        select(SpaceEvent.room_uid, next_event)
        .where(
            SpaceEvent.status == "scheduled",
            SpaceEvent.starts_at >= now,
            SpaceEvent.starts_at <= upcoming_until,
        )
        .group_by(SpaceEvent.room_uid)
        .order_by(next_event.asc())
        .limit(DISCOVERY_SOURCE_LIMIT)
    )
    upcoming_items = [
        (room_uid, starts_at)
        for room_uid, starts_at in event_result.all()
        if room_uid and starts_at
    ]

    next_occurrence = func.min(ActivityOccurrence.starts_at)
    occurrence_result = await db.execute(
        select(SpaceActivity.room_uid, next_occurrence)
        .join(ActivityOccurrence, ActivityOccurrence.activity_uid == SpaceActivity.uid)
        .where(
            SpaceActivity.status == "scheduled",
            ActivityOccurrence.status == "scheduled",
            ActivityOccurrence.starts_at >= now,
            ActivityOccurrence.starts_at <= upcoming_until,
        )
        .group_by(SpaceActivity.room_uid)
        .order_by(next_occurrence.asc())
        .limit(DISCOVERY_SOURCE_LIMIT)
    )
    upcoming_items.extend(
        (room_uid, starts_at)
        for room_uid, starts_at in occurrence_result.all()
        if room_uid and starts_at
    )
    upcoming_items.sort(key=lambda item: (item[1], str(item[0])))
    upcoming_uids: list[UUID] = []
    upcoming_seen: set[UUID] = set()
    for room_uid, _ in upcoming_items:
        if room_uid in upcoming_seen:
            continue
        upcoming_seen.add(room_uid)
        upcoming_uids.append(room_uid)
        if len(upcoming_uids) >= DISCOVERY_SOURCE_LIMIT:
            break

    shared_sources: list[list[UUID]] = []
    if viewer_tag_slugs:
        tag_match_count = func.count(func.distinct(SpaceTag.slug))
        tag_result = await db.execute(
            select(SpaceTag.room_uid, tag_match_count)
            .where(SpaceTag.slug.in_(sorted(viewer_tag_slugs)))
            .group_by(SpaceTag.room_uid)
            .order_by(tag_match_count.desc(), SpaceTag.room_uid.asc())
            .limit(DISCOVERY_SOURCE_LIMIT)
        )
        shared_sources.append([room_uid for room_uid, _ in tag_result.all()])

    if viewer_purposes:
        purpose_result = await db.execute(
            select(SpaceSettings.room_uid)
            .where(SpaceSettings.purpose.in_(sorted(viewer_purposes)))
            .order_by(SpaceSettings.updated_at.desc(), SpaceSettings.room_uid.asc())
            .limit(DISCOVERY_SOURCE_LIMIT)
        )
        shared_sources.append([room_uid for (room_uid,) in purpose_result.all()])

    shared_uids = _round_robin_unique(
        shared_sources,
        limit=DISCOVERY_SOURCE_LIMIT,
    )

    # Freshness is a fallback source large enough to keep bounded pagination
    # useful even on a quiet installation. Round-robin interleaving ensures it
    # cannot crowd out active/upcoming/shared-context candidates.
    fresh_result = await db.execute(
        select(Room.uid)
        .where(Room.is_active.is_(True))
        .order_by(Room.created_at.desc(), Room.uid.asc())
        .limit(DISCOVERY_POOL_LIMIT)
    )
    fresh_uids = [room_uid for (room_uid,) in fresh_result.all()]

    return _round_robin_unique(
        [
            membership_uids,
            recent_uids,
            upcoming_uids,
            shared_uids,
            fresh_uids,
        ],
        limit=DISCOVERY_POOL_LIMIT,
    )


async def _recent_contributor_counts(
    db: AsyncSession,
    room_uids: list[UUID],
    now: datetime,
) -> dict[UUID, int]:
    if not room_uids:
        return {}
    since = now - timedelta(hours=RECENT_ACTIVITY_HOURS)
    result = await db.execute(
        select(Message.room_uid, func.count(func.distinct(Message.author_uid)))
        .where(
            Message.room_uid.in_(room_uids),
            Message.created_at >= since,
            Message.author_uid.is_not(None),
        )
        .group_by(Message.room_uid)
    )
    return {room_uid: int(count) for room_uid, count in result.all()}


async def _upcoming_by_room(
    db: AsyncSession,
    room_uids: list[UUID],
    now: datetime,
) -> dict[UUID, dict]:
    if not room_uids:
        return {}

    until = now + timedelta(days=UPCOMING_WINDOW_DAYS)
    candidates: dict[UUID, list[dict]] = defaultdict(list)

    event_result = await db.execute(
        select(SpaceEvent.room_uid, SpaceEvent.title, SpaceEvent.starts_at)
        .where(
            SpaceEvent.room_uid.in_(room_uids),
            SpaceEvent.status == "scheduled",
            SpaceEvent.starts_at >= now,
            SpaceEvent.starts_at <= until,
        )
        .order_by(SpaceEvent.room_uid.asc(), SpaceEvent.starts_at.asc())
    )
    for room_uid, title, starts_at in event_result.all():
        candidates[room_uid].append(
            {"kind": "event", "title": title, "starts_at": starts_at}
        )

    occurrence_result = await db.execute(
        select(
            SpaceActivity.room_uid,
            SpaceActivity.title,
            ActivityOccurrence.starts_at,
        )
        .join(ActivityOccurrence, ActivityOccurrence.activity_uid == SpaceActivity.uid)
        .where(
            SpaceActivity.room_uid.in_(room_uids),
            SpaceActivity.status == "scheduled",
            ActivityOccurrence.status == "scheduled",
            ActivityOccurrence.starts_at >= now,
            ActivityOccurrence.starts_at <= until,
        )
        .order_by(SpaceActivity.room_uid.asc(), ActivityOccurrence.starts_at.asc())
    )
    for room_uid, title, starts_at in occurrence_result.all():
        candidates[room_uid].append(
            {"kind": "activity", "title": title, "starts_at": starts_at}
        )

    result: dict[UUID, dict] = {}
    for room_uid, items in candidates.items():
        result[room_uid] = min(items, key=lambda item: item["starts_at"])
    return result


def _score_space(
    space: dict,
    *,
    recent_contributors: int,
    upcoming: dict | None,
    viewer_purposes: set[str],
    viewer_tags: set[str],
    social_intent: str | None,
    now: datetime,
) -> tuple[float, list[dict]]:
    score = 0.0
    reasons: list[dict] = []

    membership = space.get("viewer_membership") or {}
    membership_status = membership.get("status")
    if membership_status == "active":
        score += 2
        reasons.append(_reason("already_member"))
    elif membership_status == "pending":
        score += 1
        reasons.append(_reason("request_pending"))

    if recent_contributors > 0:
        # Distinct recent authors are intentionally used instead of raw message
        # volume so one noisy Account cannot cheaply manufacture activity rank.
        score += 6 + min(8, recent_contributors * 2)
        reasons.append(_reason("active_conversation"))

    if upcoming:
        hours = max(0.0, (upcoming["starts_at"] - now).total_seconds() / 3600)
        score += 15 if hours <= 24 else 10 if hours <= 24 * 7 else 6
        reasons.append(_reason("upcoming_activity"))

    space_tags = {
        _normalize_topic(tag)
        for tag in (space.get("tags") or [])
        if _normalize_topic(tag)
    }
    shared_tag_count = len(space_tags & viewer_tags)
    if shared_tag_count:
        score += min(12, shared_tag_count * 4)
        reasons.append(_reason("shared_topics"))

    purpose = str(space.get("purpose") or "community")
    if purpose in viewer_purposes and membership_status != "active":
        score += 4
        reasons.append(_reason("familiar_format"))

    if purpose in INTENT_PURPOSES.get(social_intent or "", set()):
        score += 6
        reasons.append(_reason("intent_match"))

    created_at = _parse_created_at(space.get("created_at"))
    if created_at and created_at >= now - timedelta(days=14):
        score += 3
        reasons.append(_reason("new_space"))

    # Member count is a deliberately weak/capped organic context signal, never a
    # social authority score and never sourced from legacy Room.rating.
    member_count = max(0, int(space.get("member_count") or 0))
    score += min(4.0, math.log2(member_count + 1) * 0.75)

    # Score stays server-only. Client receives a compact explanation instead.
    return score, reasons[:3]


def _diversify(items: list[dict]) -> list[dict]:
    remaining = list(items)
    result: list[dict] = []

    while remaining:
        chosen_index = 0
        if len(result) >= 2:
            last_purpose = result[-1]["space"].get("purpose")
            previous_purpose = result[-2]["space"].get("purpose")
            if last_purpose == previous_purpose:
                best_score = remaining[0]["_score"]
                for index, candidate in enumerate(remaining[1:8], start=1):
                    if candidate["space"].get("purpose") == last_purpose:
                        continue
                    if best_score - candidate["_score"] <= 8:
                        chosen_index = index
                        break
        result.append(remaining.pop(chosen_index))

    return result


async def discover_spaces(
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
    viewer = UUID(str(viewer_uid))

    now = datetime.utcnow()
    viewer_purposes, viewer_tags, viewer_tag_slugs, social_intent = await _viewer_context(db, viewer)

    # Explicit search/filter mode retains the canonical bounded catalog
    # semantics. Default organic discovery instead uses multiple independent
    # bounded sources so an older Space can re-enter the pool after new social
    # activity rather than being permanently excluded by creation date.
    if query or purpose or tag or category:
        candidate_spaces = await list_spaces(
            db,
            viewer_uid=viewer,
            query=query,
            purpose=purpose,
            tag=tag,
            category=category,
            limit=DISCOVERY_POOL_LIMIT,
            offset=0,
        )
    else:
        candidate_uids = await _candidate_room_uids(
            db,
            viewer,
            viewer_purposes=viewer_purposes,
            viewer_tags=viewer_tags,
            viewer_tag_slugs=viewer_tag_slugs,
            now=now,
        )
        candidate_spaces = await list_spaces(
            db,
            viewer_uid=viewer,
            limit=DISCOVERY_POOL_LIMIT,
            offset=0,
            candidate_uids=candidate_uids,
        )

    # Eligibility is resolved by the canonical Space service before ranking;
    # candidate generation never makes a private/inactive Space visible.
    blocked_accounts = await _blocked_account_uids(db, viewer)
    eligible: list[dict] = []
    for space in candidate_spaces:
        membership = space.get("viewer_membership") or {}
        owner_uid = space.get("owner_uid")
        try:
            owner_account_uid = UUID(str(owner_uid)) if owner_uid else None
        except (TypeError, ValueError):
            owner_account_uid = None

        # Block suppresses owner-led public discovery for non-members. Existing
        # membership remains a Space/community relation and is not silently removed.
        if (
            owner_account_uid in blocked_accounts
            and membership.get("status") not in {"active", "pending"}
        ):
            continue
        eligible.append(space)

    room_uids = [UUID(str(space["uid"])) for space in eligible]
    recent_by_room = await _recent_contributor_counts(db, room_uids, now)
    upcoming_by_room = await _upcoming_by_room(db, room_uids, now)

    ranked: list[dict] = []
    for space in eligible:
        room_uid = UUID(str(space["uid"]))
        membership = space.get("viewer_membership") or {}
        is_owner = str(space.get("owner_uid") or "") == str(viewer)
        can_see_live_context = (
            space.get("visibility") == "public"
            or membership.get("status") == "active"
            or is_owner
        )
        recent_contributors = recent_by_room.get(room_uid, 0) if can_see_live_context else 0
        upcoming = upcoming_by_room.get(room_uid) if can_see_live_context else None

        score, reasons = _score_space(
            space,
            recent_contributors=recent_contributors,
            upcoming=upcoming,
            viewer_purposes=viewer_purposes,
            viewer_tags=viewer_tags,
            social_intent=social_intent,
            now=now,
        )

        discovery = {
            "algorithm": DISCOVERY_ALGORITHM,
            "reasons": reasons,
            "upcoming": {
                "kind": upcoming["kind"],
                "title": upcoming["title"],
                "starts_at": upcoming["starts_at"].isoformat(),
            }
            if upcoming
            else None,
        }
        ranked.append({"space": {**space, "discovery": discovery}, "_score": score})

    ranked.sort(
        key=lambda item: (
            -item["_score"],
            str(item["space"].get("name") or "").casefold(),
            str(item["space"].get("uid") or ""),
        )
    )
    diversified = _diversify(ranked)
    page = diversified[offset : offset + limit]
    return [item["space"] for item in page]
