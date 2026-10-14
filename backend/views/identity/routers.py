from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from components.auth.middleware import auth_middle
from components.identity.legacy import rotate_session_with_legacy_fallback
from components.identity.model import Persona
from components.identity.schemas import (
    LoginRequest,
    PersonaUpdateRequest,
    PrivacyUpdateRequest,
    ProfilesBatchRequest,
    RegisterRequest,
)
from components.identity.service import (
    authenticate_account,
    build_identity_projection,
    build_public_profile,
    get_account_by_uid,
    register_account,
    revoke_session,
    update_primary_persona,
    update_privacy,
)
from components.moderation.account_access import account_access_projection
from components.moderation.policy import assert_allowed
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


async def _identity_response(db: AsyncSession, account, tokens: dict | None = None) -> dict:
    projection = await build_identity_projection(db, account)
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


def install(app: FastAPI):
    router = APIRouter(prefix="/identity/v2", tags=["identity-v2"])

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
        # A suspended Account may authenticate into a deliberately restricted
        # session so it can inspect the sanction, appeal it, and log out. Global
        # auth middleware denies every non-exempt authenticated surface.
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
        await revoke_session(db, request.cookies.get(COOKIE_NAME))
        response.delete_cookie(COOKIE_NAME, path="/")
        return {"status": "ok"}

    @router.get("/me")
    async def me(
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        account = await get_account_by_uid(db, current_user["user_uid"])
        return await _identity_response(db, account)

    @router.post("/personas/batch")
    async def batch_personas(
        payload: ProfilesBatchRequest,
        _: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        # This endpoint is a deliberately small presence projection used by
        # realtime room/messenger surfaces. Discovery and direct profile access
        # use the stricter privacy-aware social/profile contracts.
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
            # Deliberately return 404 rather than exposing whether the target is
            # private or has a block relationship with the viewer.
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
        return {"status": "ok", **(await update_primary_persona(db, account, payload))}

    @router.patch("/privacy")
    async def patch_privacy(
        payload: PrivacyUpdateRequest,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        # Safety/privacy controls remain available for ordinary capability restrictions,
        # but account.access itself is caught earlier by auth_middle.
        account = await get_account_by_uid(db, current_user["user_uid"])
        return {"status": "ok", **(await update_privacy(db, account, payload))}

    app.include_router(router)
