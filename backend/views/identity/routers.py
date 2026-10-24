import re
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from components.auth.middleware import auth_middle
from components.identity.legacy import rotate_session_with_legacy_fallback
from components.identity.model import Persona
from components.identity.schemas import (
    LoginRequest,
    PersonaCreateRequest,
    PersonaUpdateRequest,
    PrivacyUpdateRequest,
    ProfilesBatchRequest,
    RegisterRequest,
)
from components.identity.service import (
    authenticate_account,
    build_identity_projection,
    build_public_profile,
    list_account_personas,
    create_account_persona,
    activate_account_persona,
    persona_projection,
    get_account_by_uid,
    list_account_sessions,
    register_account,
    revoke_device_sessions,
    revoke_other_sessions,
    revoke_session,
    revoke_session_by_uid,
    update_primary_persona,
    update_privacy,
)
from components.moderation.account_access import account_access_projection
from components.moderation.policy import assert_allowed
from components.realtime import RealtimeUnavailable, realtime_service
from components.reputation.public import public_reputation_projection, self_reputation_projection
from components.social.privacy import can_view_profile
from database import Database
from settings import config


COOKIE_NAME = "refresh_token"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=config.SERVER_HTTP_PROTOCOL.lower().startswith("https"),
        samesite="lax",
        max_age=config.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/",
    )


async def _identity_response(
    db: AsyncSession, account, tokens: dict | None = None,
    session_uid: str | None = None,
) -> dict:
    projection = await build_identity_projection(db, account, session_uid)
    result = {
        "status": "ok",
        **projection,
        "access_restriction": await account_access_projection(db, account.uid),
        "reputation": await self_reputation_projection(db, account.uid),
    }
    if tokens:
        result.update(
            {
                "access_token": tokens["access"],
                "token_type": "bearer",
            }
        )
    return result


async def _disconnect_sessions(
    account_uid: str,
    *,
    session_uid: str | None = None,
    device_uid: str | None = None,
    except_session_uid: str | None = None,
) -> None:
    try:
        await realtime_service.publish(
            {
                "kind": "session_control",
                "action": "disconnect",
                "account_uid": str(account_uid),
                "session_uid": str(session_uid) if session_uid else None,
                "device_uid": str(device_uid) if device_uid else None,
                "except_session_uid": str(except_session_uid) if except_session_uid else None,
                "reason": "Session revoked",
            }
        )
    except RealtimeUnavailable:
        # The DB revocation is authoritative. If Redis is degraded, existing
        # sockets cannot be pushed closed immediately, but their next HTTP/ticket
        # authorization still fails closed against IdentitySession.
        return


def install(app: FastAPI):
    router = APIRouter(prefix="/identity/v2", tags=["identity-v2"])

    @router.get("/handle-availability")
    async def handle_availability(
        handle: str,
        db: AsyncSession = Depends(Database.session_generator),
    ):
        # An advisory check only: register_account enforces the authoritative
        # case-insensitive uniqueness constraint under concurrency.
        normalized = handle.strip()
        if not re.fullmatch(r"[A-Za-z0-9_.]{3,32}", normalized):
            raise HTTPException(status_code=422, detail="Invalid handle")
        existing = await db.execute(
            select(Persona.uid).where(func.lower(Persona.handle) == normalized.casefold()).limit(1)
        )
        return {"available": existing.scalar_one_or_none() is None}

    @router.post("/register", status_code=status.HTTP_201_CREATED)
    async def register(
        payload: RegisterRequest,
        request: Request,
        response: Response,
        db: AsyncSession = Depends(Database.session_generator),
    ):
        account, tokens = await register_account(db, payload, request)
        _set_refresh_cookie(response, tokens["refresh"])
        return await _identity_response(db, account, tokens)

    @router.post("/login")
    async def login(
        payload: LoginRequest,
        request: Request,
        response: Response,
        db: AsyncSession = Depends(Database.session_generator),
    ):
        account, tokens = await authenticate_account(db, payload.identifier, payload.password, request)
        _set_refresh_cookie(response, tokens["refresh"])
        return await _identity_response(db, account, tokens)

    @router.post("/refresh")
    async def refresh(
        request: Request,
        response: Response,
        db: AsyncSession = Depends(Database.session_generator),
    ):
        refresh_token = request.cookies.get(COOKIE_NAME)
        account, tokens = await rotate_session_with_legacy_fallback(
            db, refresh_token or "", request
        )
        _set_refresh_cookie(response, tokens["refresh"])
        return {
            "status": "ok",
            "access_token": tokens["access"],
            "token_type": "bearer",
            "account_uid": str(account.uid),
            "access_restriction": await account_access_projection(db, account.uid),
        }

    @router.post("/logout")
    async def logout(
        request: Request,
        response: Response,
        db: AsyncSession = Depends(Database.session_generator),
    ):
        revoked = await revoke_session(db, request.cookies.get(COOKIE_NAME))
        response.delete_cookie(COOKIE_NAME, path="/")
        if revoked:
            await _disconnect_sessions(str(revoked.account_uid), session_uid=str(revoked.uid))
        return {"status": "ok"}

    @router.get("/me")
    async def me(
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        account = await get_account_by_uid(db, current_user["user_uid"])
        return await _identity_response(db, account, session_uid=current_user.get("session_uid"))

    @router.get("/sessions")
    async def sessions(
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        devices = await list_account_sessions(
            db,
            current_user["user_uid"],
            current_user.get("session_uid"),
        )
        return {
            "status": "ok",
            "current_session_uid": current_user.get("session_uid"),
            "current_device_uid": current_user.get("device_uid"),
            "devices": devices,
        }

    @router.delete("/sessions/{session_uid}")
    async def delete_session(
        session_uid: UUID,
        response: Response,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        revoked = await revoke_session_by_uid(db, current_user["user_uid"], session_uid)
        if not revoked:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_type": "session_not_found"},
            )
        is_current = str(session_uid) == str(current_user.get("session_uid") or "")
        if is_current:
            response.delete_cookie(COOKIE_NAME, path="/")
        await _disconnect_sessions(current_user["user_uid"], session_uid=str(session_uid))
        return {"status": "ok", "current_revoked": is_current}

    @router.delete("/devices/{device_uid}")
    async def delete_device_sessions(
        device_uid: UUID,
        response: Response,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        revoked = await revoke_device_sessions(db, current_user["user_uid"], device_uid)
        is_current = str(device_uid) == str(current_user.get("device_uid") or "")
        if is_current:
            response.delete_cookie(COOKIE_NAME, path="/")
        if revoked:
            await _disconnect_sessions(current_user["user_uid"], device_uid=str(device_uid))
        return {"status": "ok", "revoked": revoked, "current_revoked": is_current and revoked > 0}

    @router.post("/sessions/revoke-others")
    async def delete_other_sessions(
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        current_session_uid = current_user.get("session_uid")
        if not current_session_uid:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error_type": "session_identity_unavailable"},
            )
        revoked = await revoke_other_sessions(db, current_user["user_uid"], current_session_uid)
        if revoked:
            await _disconnect_sessions(
                current_user["user_uid"],
                except_session_uid=current_session_uid,
            )
        return {"status": "ok", "revoked": revoked}

    @router.get("/personas")
    async def list_personas(
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        account = await get_account_by_uid(db, current_user["user_uid"])
        return {
            "status": "ok",
            **await list_account_personas(db, account.uid, current_user.get("session_uid")),
        }

    @router.post("/personas", status_code=status.HTTP_201_CREATED)
    async def create_persona(
        payload: PersonaCreateRequest,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        await assert_allowed(db, current_user["user_uid"], "profile.edit")
        account = await get_account_by_uid(db, current_user["user_uid"])
        persona = await create_account_persona(db, account, payload)
        return {"status": "ok", "persona": persona_projection(persona)}

    @router.post("/personas/{persona_uid}/activate")
    async def activate_persona(
        persona_uid: UUID,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        account = await get_account_by_uid(db, current_user["user_uid"])
        await activate_account_persona(
            db, account.uid, current_user.get("session_uid"), persona_uid
        )
        return await _identity_response(
            db, account, session_uid=current_user.get("session_uid")
        )

    @router.post("/personas/batch")
    async def batch_personas(
        payload: ProfilesBatchRequest,
        _: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        requested = list(dict.fromkeys(payload.account_uids))
        result = await db.execute(
            select(Persona).where(
                Persona.account_uid.in_(requested),
                Persona.is_primary.is_(True),
            )
        )
        personas_by_account = {persona.account_uid: persona for persona in result.scalars().all()}
        personas = []
        for account_uid in requested:
            persona = personas_by_account.get(account_uid)
            if not persona:
                continue
            personas.append(
                {
                    "uid": str(account_uid),
                    "persona_uid": str(persona.uid),
                    "handle": persona.handle,
                    "display_name": persona.display_name,
                    "avatar": persona.avatar,
                    "social_intent": persona.social_intent,
                }
            )
        return {"status": "ok", "personas": personas}

    @router.get("/profiles/{account_uid}")
    async def public_profile(
        account_uid: str,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        account = await get_account_by_uid(db, account_uid)
        if not await can_view_profile(db, current_user["user_uid"], account.uid):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_type": "profile_not_available"},
            )
        profile = await build_public_profile(db, account, current_user["user_uid"])
        profile["reputation"] = await public_reputation_projection(db, account.uid)
        return {"status": "ok", "profile": profile}

    @router.patch("/persona")
    async def patch_persona(
        payload: PersonaUpdateRequest,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        await assert_allowed(db, current_user["user_uid"], "profile.edit")
        account = await get_account_by_uid(db, current_user["user_uid"])
        return {"status": "ok", **(await update_primary_persona(db, account, payload, current_user.get("session_uid")))}

    @router.patch("/privacy")
    async def patch_privacy(
        payload: PrivacyUpdateRequest,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        account = await get_account_by_uid(db, current_user["user_uid"])
        return {"status": "ok", **(await update_privacy(db, account, payload, current_user.get("session_uid")))}

    app.include_router(router)
