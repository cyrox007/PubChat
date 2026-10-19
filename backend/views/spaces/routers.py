from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from components.auth.middleware import auth_middle
from components.moderation.policy import assert_allowed
from components.space.content_schemas import (
    SpaceEventCreateRequest,
    SpaceEventUpdateRequest,
    SpaceRuleCreateRequest,
    SpaceRuleUpdateRequest,
)
from components.space.content_service import (
    create_event,
    create_rule,
    delete_event,
    delete_rule,
    list_events,
    list_history,
    list_rules,
    update_event,
    update_rule,
)
from components.space.invitation_schemas import SpaceInvitationActionRequest
from components.space.invitation_service import (
    create_invitation,
    list_invitations,
    respond_to_invitation,
    revoke_invitation,
)
from components.space.membership_schemas import (
    SpaceMembershipActionRequest,
    SpaceMembershipRoleFilter,
    SpaceMembershipStatusFilter,
)
from components.space.membership_service import list_members_page, manage_membership
from components.space.model import SpaceSettings
from components.space.schemas import (
    SpaceCreateRequest,
    SpaceMembershipRoleUpdateRequest,
    SpacePurpose,
    SpaceUpdateRequest,
)
from components.space.service import (
    archive_space,
    create_space,
    get_space,
    join_space,
    leave_space,
    list_spaces,
    update_member_role,
    update_space,
)
from database import Database


def install(app: FastAPI) -> None:
    router = APIRouter(prefix="/spaces/v1", tags=["spaces-v1"])

    @router.get("")
    async def index(
        q: Optional[str] = Query(default=None, max_length=80),
        purpose: Optional[SpacePurpose] = None,
        tag: Optional[str] = Query(default=None, max_length=40),
        category: Optional[str] = Query(default=None, max_length=40, pattern=r"^[a-z][a-z0-9-]*$"),
        limit: int = Query(default=30, ge=1, le=50),
        offset: int = Query(default=0, ge=0),
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        spaces = await list_spaces(
            db,
            viewer_uid=current_user["user_uid"],
            query=q,
            purpose=purpose,
            tag=tag,
            category=category,
            limit=limit,
            offset=offset,
        )
        return {
            "status": "ok",
            "spaces": spaces,
            "pagination": {"limit": limit, "offset": offset, "count": len(spaces)},
        }

    @router.post("", status_code=status.HTTP_201_CREATED)
    async def create(
        payload: SpaceCreateRequest,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        await assert_allowed(db, current_user["user_uid"], "space.create")
        space = await create_space(db, current_user["user_uid"], payload)
        return {"status": "ok", "space": space}

    # Keep collection-level invitation routes above /{space_uid}; otherwise the
    # dynamic UUID route would consume the literal "invitations" segment.
    @router.get("/invitations")
    async def invitations(
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        items, total = await list_invitations(
            db,
            viewer_uid=current_user["user_uid"],
            limit=limit,
            offset=offset,
        )
        return {
            "status": "ok",
            "invitations": items,
            "pagination": {"limit": limit, "offset": offset, "count": len(items), "total": total},
        }

    @router.patch("/invitations/{invitation_uid}")
    async def invitation_action(
        invitation_uid: UUID,
        payload: SpaceInvitationActionRequest,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        invitation = await respond_to_invitation(
            db,
            invitation_uid=invitation_uid,
            viewer_uid=current_user["user_uid"],
            action=payload.action,
        )
        return {"status": "ok", "invitation": invitation}

    @router.get("/{space_uid}")
    async def detail(
        space_uid: UUID,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        space = await get_space(db, space_uid, current_user["user_uid"])
        return {"status": "ok", "space": space}

    @router.patch("/{space_uid}")
    async def patch(
        space_uid: UUID,
        payload: SpaceUpdateRequest,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        changes = payload.model_dump(exclude_unset=True)
        settings = await db.get(SpaceSettings, space_uid)
        current_visibility = settings.visibility if settings else "public"
        current_join_policy = settings.join_policy if settings else "open"
        next_visibility = changes.get("visibility", current_visibility)
        next_join_policy = changes.get("join_policy", current_join_policy)
        if next_visibility == "private" and next_join_policy != "invite":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error_type": "private_space_must_be_invite_only"},
            )

        space = await update_space(db, space_uid, current_user["user_uid"], payload)
        return {"status": "ok", "space": space}

    @router.delete("/{space_uid}")
    async def archive(
        space_uid: UUID,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        await archive_space(db, space_uid, current_user["user_uid"])
        return {"status": "ok"}

    @router.post("/{space_uid}/join")
    async def join(
        space_uid: UUID,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        await assert_allowed(
            db,
            current_user["user_uid"],
            "space.join",
            scope_type="space",
            scope_uid=space_uid,
        )
        space = await join_space(db, space_uid, current_user["user_uid"])
        return {"status": "ok", "space": space}

    @router.delete("/{space_uid}/membership")
    async def leave(
        space_uid: UUID,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        await leave_space(db, space_uid, current_user["user_uid"])
        return {"status": "ok"}

    @router.get("/{space_uid}/members")
    async def members(
        space_uid: UUID,
        membership_status: SpaceMembershipStatusFilter = Query(default="active", alias="status"),
        role: Optional[SpaceMembershipRoleFilter] = None,
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        items, total = await list_members_page(
            db,
            space_uid=space_uid,
            viewer_uid=current_user["user_uid"],
            membership_status=membership_status,
            role=role,
            limit=limit,
            offset=offset,
        )
        return {
            "status": "ok",
            "members": items,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "count": len(items),
                "total": total,
            },
        }

    @router.patch("/{space_uid}/members/{account_uid}")
    async def patch_member_role(
        space_uid: UUID,
        account_uid: UUID,
        payload: SpaceMembershipRoleUpdateRequest,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        membership = await update_member_role(
            db,
            space_uid=space_uid,
            target_account_uid=account_uid,
            viewer_uid=current_user["user_uid"],
            role=payload.role,
        )
        return {"status": "ok", "membership": membership}

    @router.patch("/{space_uid}/members/{account_uid}/membership")
    async def patch_membership(
        space_uid: UUID,
        account_uid: UUID,
        payload: SpaceMembershipActionRequest,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        membership = await manage_membership(
            db,
            space_uid=space_uid,
            target_account_uid=account_uid,
            viewer_uid=current_user["user_uid"],
            action=payload.action,
        )
        return {"status": "ok", "membership": membership}

    @router.get("/{space_uid}/rules")
    async def rules(
        space_uid: UUID,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        return {"status": "ok", "rules": await list_rules(db, space_uid, current_user["user_uid"])}

    @router.post("/{space_uid}/rules", status_code=status.HTTP_201_CREATED)
    async def add_rule(
        space_uid: UUID,
        payload: SpaceRuleCreateRequest,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        return {"status": "ok", "rule": await create_rule(db, space_uid, current_user["user_uid"], payload)}

    @router.patch("/{space_uid}/rules/{rule_uid}")
    async def patch_rule(
        space_uid: UUID,
        rule_uid: UUID,
        payload: SpaceRuleUpdateRequest,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        return {"status": "ok", "rule": await update_rule(db, space_uid, rule_uid, current_user["user_uid"], payload)}

    @router.delete("/{space_uid}/rules/{rule_uid}")
    async def remove_rule(
        space_uid: UUID,
        rule_uid: UUID,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        await delete_rule(db, space_uid, rule_uid, current_user["user_uid"])
        return {"status": "ok"}

    @router.get("/{space_uid}/events")
    async def events(
        space_uid: UUID,
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        items, total = await list_events(db, space_uid, current_user["user_uid"], limit, offset)
        return {"status": "ok", "events": items, "pagination": {"limit": limit, "offset": offset, "count": len(items), "total": total}}

    @router.post("/{space_uid}/events", status_code=status.HTTP_201_CREATED)
    async def add_event(
        space_uid: UUID,
        payload: SpaceEventCreateRequest,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        return {"status": "ok", "event": await create_event(db, space_uid, current_user["user_uid"], payload)}

    @router.patch("/{space_uid}/events/{event_uid}")
    async def patch_event(
        space_uid: UUID,
        event_uid: UUID,
        payload: SpaceEventUpdateRequest,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        return {"status": "ok", "event": await update_event(db, space_uid, event_uid, current_user["user_uid"], payload)}

    @router.delete("/{space_uid}/events/{event_uid}")
    async def remove_event(
        space_uid: UUID,
        event_uid: UUID,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        await delete_event(db, space_uid, event_uid, current_user["user_uid"])
        return {"status": "ok"}

    @router.get("/{space_uid}/history")
    async def history(
        space_uid: UUID,
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        items, total = await list_history(db, space_uid, current_user["user_uid"], limit, offset)
        return {"status": "ok", "history": items, "pagination": {"limit": limit, "offset": offset, "count": len(items), "total": total}}

    @router.post("/{space_uid}/invitations/{account_uid}", status_code=status.HTTP_201_CREATED)
    async def invite(
        space_uid: UUID,
        account_uid: UUID,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        await assert_allowed(
            db,
            current_user["user_uid"],
            "invitation.send",
            scope_type="space",
            scope_uid=space_uid,
        )
        invitation = await create_invitation(
            db,
            space_uid=space_uid,
            invitee_uid=account_uid,
            viewer_uid=current_user["user_uid"],
        )
        return {"status": "ok", "invitation": invitation}

    @router.delete("/{space_uid}/invitations/{account_uid}")
    async def revoke_invite(
        space_uid: UUID,
        account_uid: UUID,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        await revoke_invitation(
            db,
            space_uid=space_uid,
            invitee_uid=account_uid,
            viewer_uid=current_user["user_uid"],
        )
        return {"status": "ok"}

    app.include_router(router)
