"""Admin-only moderation dictionary management. No message contents stored."""
from fastapi import APIRouter, Depends, FastAPI, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from components.auth.permissions import require_platform_permission
from components.identity.model import Account
from components.moderation.lexicon_schemas import (
    LexiconActivate, LexiconRevisionCreate, LexiconSimulate,
)
from components.moderation.lexicon_service import (
    activate_revision, create_revision, get_revision, list_policy,
    policy_audit, simulate_policy,
)
from database import Database


async def require_lexicon_editor(request: Request) -> Account:
    return await require_platform_permission(request, "moderation.policy.manage")


def install(app: FastAPI) -> None:
    router = APIRouter(prefix="/trust-safety/v1/lexicon", tags=["trust-safety-v1"])

    @router.get("")
    async def current(
        _: Account = Depends(require_lexicon_editor),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        return {"status": "ok", "policy": await list_policy(db)}

    @router.get("/revisions/{revision}")
    async def revision_detail(
        revision: int,
        _: Account = Depends(require_lexicon_editor),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        return {"status": "ok", "revision": await get_revision(db, revision)}

    @router.post("/revisions", status_code=status.HTTP_201_CREATED)
    async def create_draft(
        payload: LexiconRevisionCreate,
        actor: Account = Depends(require_lexicon_editor),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        return {"status": "ok", "revision": await create_revision(db, actor.uid, payload)}

    @router.post("/activate")
    async def activate(
        payload: LexiconActivate,
        actor: Account = Depends(require_lexicon_editor),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        return {"status": "ok", "policy": await activate_revision(db, actor.uid, payload)}

    @router.post("/simulate")
    async def simulate(
        payload: LexiconSimulate,
        _: Account = Depends(require_lexicon_editor),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        return {"status": "ok", "simulation": await simulate_policy(db, payload.text, payload.revision)}

    @router.get("/audit")
    async def audit(
        limit: int = Query(default=50, ge=1, le=100),
        _: Account = Depends(require_lexicon_editor),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        return {"status": "ok", "events": await policy_audit(db, limit=limit)}

    app.include_router(router)
