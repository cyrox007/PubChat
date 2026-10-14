import re
from collections import defaultdict
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from components.identity.model import Account, Persona
from components.reputation.service import ensure_space_creation_privilege
from components.room.model import Room, RoomBan, RoomMember
from components.space.capacity import assert_space_has_capacity, lock_space_admission_policy
from components.space.model import SpaceMembership, SpaceSettings, SpaceTag
from components.space.schemas import SpaceCreateRequest, SpaceUpdateRequest


DEFAULT_PURPOSE = "community"
DEFAULT_VISIBILITY = "public"
DEFAULT_JOIN_POLICY = "open"
DEFAULT_MEMBER_LIMIT = 250


def _slugify_tag(value: str) -> str:
    normalized = re.sub(r"\s+", " ", str(value)).strip().casefold()
    normalized = re.sub(r"[^\w-]+", "-", normalized, flags=re.UNICODE).strip("-_")
    return normalized[:64]


async def _load_active_room_by_uid(
    db: AsyncSession,
    space_uid: UUID,
) -> Room:
    result = await db.execute(
        select(Room)
        .where(
            Room.uid == space_uid,
            Room.is_active.is_(True),
        )
        .limit(1)
    )
    room = result.scalar_one_or_none()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_type": "space_not_found"},
        )
    return room


async def _get_account(db: AsyncSession, account_uid: UUID | str) -> Account:
    try:
        normalized_uid = UUID(str(account_uid))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_type": "invalid_account"},
        ) from exc

    account = await db.get(Account, normalized_uid)
    if not account or account.status != "active" or account.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error_type": "account_unavailable"},
        )
    if not account.legacy_user_uid:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_type": "identity_bridge_missing"},
        )
    return account


async def _replace_tags(db: AsyncSession, room_uid: UUID, tags: list[str]) -> None:
    await db.execute(delete(SpaceTag).where(SpaceTag.room_uid == room_uid))
    seen = set()
    for label in tags:
        slug = _slugify_tag(label)
        if not slug or slug in seen:
            continue
        seen.add(slug)
        db.add(SpaceTag(room_uid=room_uid, slug=slug, label=label[:64]))


async def _sync_legacy_membership(
    db: AsyncSession,
    room_uid: UUID,
    account: Account,
    role: str = "member",
) -> None:
    legacy_uid = account.legacy_user_uid
    if not legacy_uid:
        return

    result = await db.execute(
        select(RoomMember)
        .where(RoomMember.room_uid == room_uid, RoomMember.user_uid == legacy_uid)
        .order_by(RoomMember.id.asc())
    )
    legacy_members = result.scalars().all()
    legacy_role = "moderator" if role == "moderator" else "member"

    if legacy_members:
        keeper = legacy_members[0]
        keeper.role = legacy_role
        keeper.is_banned = False
        for duplicate in legacy_members[1:]:
            await db.delete(duplicate)
        return

    db.add(
        RoomMember(
            room_uid=room_uid,
            user_uid=legacy_uid,
            role=legacy_role,
            is_banned=False,
        )
    )


async def _owner_account_map(
    db: AsyncSession,
    owner_legacy_uids: list[UUID],
) -> tuple[dict[UUID, Account], dict[UUID, Persona]]:
    if not owner_legacy_uids:
        return {}, {}

    result = await db.execute(
        select(Account).where(
            or_(
                Account.legacy_user_uid.in_(owner_legacy_uids),
                Account.uid.in_(owner_legacy_uids),
            )
        )
    )
    accounts = result.scalars().all()

    by_any_uid: dict[UUID, Account] = {}
    for account in accounts:
        by_any_uid[account.uid] = account
        if account.legacy_user_uid:
            by_any_uid[account.legacy_user_uid] = account

    personas_by_account: dict[UUID, Persona] = {}
    if accounts:
        personas_result = await db.execute(
            select(Persona).where(
                Persona.account_uid.in_([account.uid for account in accounts]),
                Persona.is_primary.is_(True),
            )
        )
        personas_by_account = {
            persona.account_uid: persona for persona in personas_result.scalars().all()
        }

    return by_any_uid, personas_by_account


async def build_space_projections(
    db: AsyncSession,
    rooms: list[Room],
    viewer_account_uid: UUID,
) -> list[dict]:
    if not rooms:
        return []

    room_uids = [room.uid for room in rooms]
    owner_legacy_uids = [room.owner_uid for room in rooms if room.owner_uid]

    settings_result = await db.execute(
        select(SpaceSettings).where(SpaceSettings.room_uid.in_(room_uids))
    )
    settings_by_room = {item.room_uid: item for item in settings_result.scalars().all()}

    tags_result = await db.execute(
        select(SpaceTag)
        .where(SpaceTag.room_uid.in_(room_uids))
        .order_by(SpaceTag.label.asc())
    )
    tags_by_room: dict[UUID, list[str]] = defaultdict(list)
    for tag in tags_result.scalars().all():
        tags_by_room[tag.room_uid].append(tag.label)

    memberships_result = await db.execute(
        select(SpaceMembership).where(
            SpaceMembership.room_uid.in_(room_uids),
            SpaceMembership.account_uid == viewer_account_uid,
        )
    )
    viewer_membership_by_room = {
        item.room_uid: item for item in memberships_result.scalars().all()
    }

    moderators_result = await db.execute(
        select(SpaceMembership.room_uid, SpaceMembership.account_uid).where(
            SpaceMembership.room_uid.in_(room_uids),
            SpaceMembership.role == "moderator",
            SpaceMembership.status == "active",
        )
    )
    moderators_by_room: dict[UUID, list[str]] = defaultdict(list)
    for room_uid, account_uid in moderators_result.all():
        moderators_by_room[room_uid].append(str(account_uid))

    count_result = await db.execute(
        select(SpaceMembership.room_uid, func.count(SpaceMembership.uid))
        .where(
            SpaceMembership.room_uid.in_(room_uids),
            SpaceMembership.status == "active",
        )
        .group_by(SpaceMembership.room_uid)
    )
    member_count_by_room = {room_uid: count for room_uid, count in count_result.all()}

    owner_accounts_by_uid, owner_personas = await _owner_account_map(db, owner_legacy_uids)

    projections = []
    for room in rooms:
        settings = settings_by_room.get(room.uid)
        membership = viewer_membership_by_room.get(room.uid)
        owner_account = owner_accounts_by_uid.get(room.owner_uid)
        owner_account_uid = owner_account.uid if owner_account else room.owner_uid
        owner_persona = owner_personas.get(owner_account_uid)

        tags = list(tags_by_room.get(room.uid, []))
        if not tags and room.tags:
            tags = [tag.strip() for tag in str(room.tags).split(",") if tag.strip()]

        is_owner = bool(owner_account_uid and str(owner_account_uid) == str(viewer_account_uid))
        can_manage = is_owner or bool(
            membership
            and membership.status == "active"
            and membership.role in {"owner", "moderator"}
        )

        projections.append(
            {
                "uid": str(room.uid),
                "name": room.name,
                "description": room.description,
                "purpose": settings.purpose if settings else DEFAULT_PURPOSE,
                "visibility": settings.visibility if settings else DEFAULT_VISIBILITY,
                "join_policy": settings.join_policy if settings else DEFAULT_JOIN_POLICY,
                "language": settings.language if settings else None,
                "member_limit": settings.member_limit if settings else DEFAULT_MEMBER_LIMIT,
                "region": room.region,
                "country": room.country,
                "tags": tags,
                "owner_uid": str(owner_account_uid) if owner_account_uid else None,
                "owner": {
                    "uid": str(owner_account_uid),
                    "handle": owner_persona.handle if owner_persona else None,
                    "display_name": owner_persona.display_name if owner_persona else None,
                    "avatar": owner_persona.avatar if owner_persona else None,
                }
                if owner_account_uid
                else None,
                "member_count": int(member_count_by_room.get(room.uid, 0)),
                "viewer_membership": {
                    "role": membership.role,
                    "status": membership.status,
                }
                if membership
                else None,
                "moderators": moderators_by_room.get(room.uid, []),
                "can_manage": can_manage,
                "created_at": room.created_at.isoformat() if room.created_at else None,
            }
        )

    return projections


async def list_spaces(
    db: AsyncSession,
    viewer_uid: UUID | str,
    query: str | None = None,
    purpose: str | None = None,
    tag: str | None = None,
    limit: int = 30,
    offset: int = 0,
    candidate_uids: list[UUID] | None = None,
) -> list[dict]:
    account = await _get_account(db, viewer_uid)

    viewer_membership_exists = (
        select(SpaceMembership.uid)
        .where(
            SpaceMembership.room_uid == Room.uid,
            SpaceMembership.account_uid == account.uid,
            SpaceMembership.status.in_(["active", "pending"]),
        )
        .exists()
    )

    stmt = (
        select(Room)
        .outerjoin(SpaceSettings, SpaceSettings.room_uid == Room.uid)
        .where(
            Room.is_active.is_(True),
            or_(
                func.coalesce(SpaceSettings.visibility, DEFAULT_VISIBILITY) == "public",
                Room.owner_uid == account.legacy_user_uid,
                viewer_membership_exists,
            ),
        )
    )

    if candidate_uids is not None:
        if not candidate_uids:
            return []
        stmt = stmt.where(Room.uid.in_(candidate_uids))

    if query:
        normalized_query = query.strip()
        if normalized_query:
            pattern = f"%{normalized_query}%"
            stmt = stmt.where(or_(Room.name.ilike(pattern), Room.description.ilike(pattern)))

    if purpose:
        stmt = stmt.where(func.coalesce(SpaceSettings.purpose, DEFAULT_PURPOSE) == purpose)

    if tag:
        normalized_tag = _slugify_tag(tag)
        normalized_label = tag.strip().casefold()
        tag_exists = (
            select(SpaceTag.slug)
            .where(
                SpaceTag.room_uid == Room.uid,
                or_(
                    SpaceTag.slug == normalized_tag,
                    func.lower(SpaceTag.label) == normalized_label,
                ),
            )
            .exists()
        )
        stmt = stmt.where(tag_exists)

    stmt = stmt.order_by(Room.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    rooms = result.scalars().unique().all()
    return await build_space_projections(db, rooms, account.uid)


async def get_space(
    db: AsyncSession,
    space_uid: UUID,
    viewer_uid: UUID | str,
) -> dict:
    account = await _get_account(db, viewer_uid)
    result = await db.execute(
        select(Room).where(Room.uid == space_uid, Room.is_active.is_(True)).limit(1)
    )
    room = result.scalar_one_or_none()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_type": "space_not_found"},
        )

    projection = (await build_space_projections(db, [room], account.uid))[0]
    membership = projection.get("viewer_membership")
    if projection["visibility"] == "private" and not (
        projection["owner_uid"] == str(account.uid)
        or (membership and membership.get("status") == "active")
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error_type": "space_private"},
        )
    return projection


async def create_space(
    db: AsyncSession,
    viewer_uid: UUID | str,
    payload: SpaceCreateRequest,
) -> dict:
    account = await _get_account(db, viewer_uid)
    await ensure_space_creation_privilege(db, account)

    room = Room(
        name=payload.name,
        description=payload.description,
        region=payload.region,
        country=payload.country,
        tags=",".join(payload.tags),
        owner_uid=account.legacy_user_uid,
        rating=0,
        is_active=True,
    )
    db.add(room)
    await db.flush()

    db.add(
        SpaceSettings(
            room_uid=room.uid,
            purpose=payload.purpose,
            visibility=payload.visibility,
            join_policy=payload.join_policy,
            language=payload.language,
            member_limit=payload.member_limit,
        )
    )
    db.add(
        SpaceMembership(
            room_uid=room.uid,
            account_uid=account.uid,
            role="owner",
            status="active",
            joined_at=room.created_at or datetime.utcnow(),
        )
    )
    await _replace_tags(db, room.uid, payload.tags)
    await _sync_legacy_membership(db, room.uid, account, role="member")

    await db.commit()
    await db.refresh(room)
    return (await build_space_projections(db, [room], account.uid))[0]


async def _require_owner(
    db: AsyncSession,
    room: Room,
    account: Account,
) -> SpaceMembership | None:
    result = await db.execute(
        select(SpaceMembership)
        .where(
            SpaceMembership.room_uid == room.uid,
            SpaceMembership.account_uid == account.uid,
        )
        .limit(1)
    )
    membership = result.scalar_one_or_none()

    if room.owner_uid == account.legacy_user_uid:
        return membership
    if membership and membership.status == "active" and membership.role == "owner":
        return membership

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={"error_type": "space_owner_required"},
    )


async def update_space(
    db: AsyncSession,
    space_uid: UUID,
    viewer_uid: UUID | str,
    payload: SpaceUpdateRequest,
) -> dict:
    account = await _get_account(db, viewer_uid)
    room = await _load_active_room_by_uid(db, space_uid)
    await _require_owner(db, room, account)

    settings = await db.get(SpaceSettings, room.uid)
    if not settings:
        settings = SpaceSettings(room_uid=room.uid)
        db.add(settings)
        await db.flush()

    changes = payload.model_dump(exclude_unset=True)
    next_visibility = changes.get("visibility", settings.visibility)
    next_join_policy = changes.get("join_policy", settings.join_policy)
    if next_visibility == "private" and next_join_policy == "open":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"error_type": "invalid_space_policy"},
        )

    for field in ("name", "description", "region", "country"):
        if field in changes:
            setattr(room, field, changes[field])

    for field in ("purpose", "visibility", "join_policy", "language", "member_limit"):
        if field in changes:
            setattr(settings, field, changes[field])

    if "tags" in changes:
        tags = changes["tags"] or []
        room.tags = ",".join(tags)
        await _replace_tags(db, room.uid, tags)

    settings.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(room)
    return (await build_space_projections(db, [room], account.uid))[0]


async def archive_space(
    db: AsyncSession,
    space_uid: UUID,
    viewer_uid: UUID | str,
) -> None:
    account = await _get_account(db, viewer_uid)
    room = await _load_active_room_by_uid(db, space_uid)

    await _require_owner(db, room, account)
    room.is_active = False
    await db.commit()


async def join_space(
    db: AsyncSession,
    space_uid: UUID,
    viewer_uid: UUID | str,
) -> dict:
    account = await _get_account(db, viewer_uid)
    room = await _load_active_room_by_uid(db, space_uid)

    result = await db.execute(
        select(SpaceMembership)
        .where(
            SpaceMembership.room_uid == room.uid,
            SpaceMembership.account_uid == account.uid,
        )
        .limit(1)
    )
    membership = result.scalar_one_or_none()

    if membership and membership.status == "active":
        return (await build_space_projections(db, [room], account.uid))[0]

    # Every path that can make a membership active serializes on the same
    # SpaceSettings row. Re-read this Account's membership after acquiring the
    # lock so two concurrent joins from the same Account remain idempotent.
    policy = await lock_space_admission_policy(
        db,
        room.uid,
        default_join_policy=DEFAULT_JOIN_POLICY,
        default_member_limit=DEFAULT_MEMBER_LIMIT,
    )
    result = await db.execute(
        select(SpaceMembership)
        .where(
            SpaceMembership.room_uid == room.uid,
            SpaceMembership.account_uid == account.uid,
        )
        .limit(1)
    )
    membership = result.scalar_one_or_none()
    if membership and membership.status == "active":
        await db.commit()
        return (await build_space_projections(db, [room], account.uid))[0]

    join_policy = policy.join_policy

    if join_policy == "invite" and room.owner_uid != account.legacy_user_uid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error_type": "space_invite_only"},
        )

    if await RoomBan.is_user_banned(db, room.uid, account.legacy_user_uid):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error_type": "space_access_restricted"},
        )

    target_status = (
        "active"
        if join_policy == "open" or room.owner_uid == account.legacy_user_uid
        else "pending"
    )

    if target_status == "active":
        await assert_space_has_capacity(
            db,
            room.uid,
            member_limit=policy.member_limit,
        )

    if membership:
        if membership.role == "owner":
            target_status = "active"
        membership.status = target_status
        membership.updated_at = datetime.utcnow()
    else:
        membership = SpaceMembership(
            room_uid=room.uid,
            account_uid=account.uid,
            role="owner" if room.owner_uid == account.legacy_user_uid else "member",
            status=target_status,
        )
        db.add(membership)

    if target_status == "active":
        await _sync_legacy_membership(db, room.uid, account, role=membership.role)

    await db.commit()
    return (await build_space_projections(db, [room], account.uid))[0]


async def leave_space(
    db: AsyncSession,
    space_uid: UUID,
    viewer_uid: UUID | str,
) -> None:
    account = await _get_account(db, viewer_uid)
    room = await _load_active_room_by_uid(db, space_uid)
    if room.owner_uid == account.legacy_user_uid:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_type": "space_owner_cannot_leave"},
        )

    result = await db.execute(
        select(SpaceMembership)
        .where(
            SpaceMembership.room_uid == room.uid,
            SpaceMembership.account_uid == account.uid,
        )
        .limit(1)
    )
    membership = result.scalar_one_or_none()
    if not membership:
        return

    membership.status = "left"
    membership.role = "member"
    membership.updated_at = datetime.utcnow()

    legacy_result = await db.execute(
        select(RoomMember).where(
            RoomMember.room_uid == room.uid,
            RoomMember.user_uid == account.legacy_user_uid,
        )
    )
    for legacy_member in legacy_result.scalars().all():
        await db.delete(legacy_member)

    await db.commit()


async def list_space_members(
    db: AsyncSession,
    space_uid: UUID,
    viewer_uid: UUID | str,
) -> list[dict]:
    await get_space(db, space_uid, viewer_uid)

    result = await db.execute(
        select(SpaceMembership, Persona)
        .outerjoin(
            Persona,
            (Persona.account_uid == SpaceMembership.account_uid)
            & Persona.is_primary.is_(True),
        )
        .where(
            SpaceMembership.room_uid == space_uid,
            SpaceMembership.status == "active",
        )
        .order_by(
            SpaceMembership.role.asc(),
            SpaceMembership.joined_at.asc(),
        )
        .limit(250)
    )

    members = []
    for membership, persona in result.all():
        members.append(
            {
                "account_uid": str(membership.account_uid),
                "role": membership.role,
                "status": membership.status,
                "joined_at": membership.joined_at.isoformat() if membership.joined_at else None,
                "persona": {
                    "uid": str(membership.account_uid),
                    "persona_uid": str(persona.uid) if persona else None,
                    "handle": persona.handle if persona else None,
                    "display_name": persona.display_name if persona else None,
                    "avatar": persona.avatar if persona else None,
                    "social_intent": persona.social_intent if persona else None,
                },
            }
        )
    return members


async def update_member_role(
    db: AsyncSession,
    space_uid: UUID,
    target_account_uid: UUID,
    viewer_uid: UUID | str,
    role: str,
) -> dict:
    owner_account = await _get_account(db, viewer_uid)
    room = await _load_active_room_by_uid(db, space_uid)

    await _require_owner(db, room, owner_account)

    target_account = await db.get(Account, target_account_uid)
    if not target_account or target_account.status != "active":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_type": "member_not_found"},
        )
    if room.owner_uid == target_account.legacy_user_uid:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_type": "cannot_change_owner_role"},
        )

    result = await db.execute(
        select(SpaceMembership)
        .where(
            SpaceMembership.room_uid == room.uid,
            SpaceMembership.account_uid == target_account.uid,
            SpaceMembership.status == "active",
        )
        .limit(1)
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error_type": "member_not_found"},
        )

    membership.role = role
    membership.updated_at = datetime.utcnow()
    await _sync_legacy_membership(db, room.uid, target_account, role=role)
    await db.commit()

    return {
        "account_uid": str(target_account.uid),
        "role": membership.role,
        "status": membership.status,
    }
