"""Persist moderated dictionary revisions under a singleton PostgreSQL row lock.

No revision activates automatically: the entire rollout is OFF/SHADOW-only until
separate content-write enforcement #146 is audited and accepted.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from components.moderation.lexicon_matcher import simulate_rules
from components.moderation.lexicon_model import (
    ModerationLexiconAudit, ModerationLexiconRevision, ModerationLexiconState,
)
from components.moderation.lexicon_schemas import LexiconActivate, LexiconRevisionCreate


def _missing_revision() -> HTTPException:
    return HTTPException(status_code=404, detail={"error_type": "lexicon_revision_not_found"})


async def _state(db: AsyncSession, *, lock: bool = False) -> ModerationLexiconState:
    statement = select(ModerationLexiconState).where(ModerationLexiconState.id == 1)
    if lock:
        statement = statement.with_for_update()
    state = (await db.execute(statement)).scalar_one_or_none()
    if state is None:
        raise HTTPException(status_code=503, detail={"error_type": "lexicon_migration_required"})
    return state


def _revision_projection(row: ModerationLexiconRevision) -> dict:
    return {
        "revision": row.revision,
        "rules": row.rules,
        "reason": row.reason,
        "created_at": row.created_at.isoformat(),
        "created_by_account_uid": str(row.created_by_account_uid) if row.created_by_account_uid else None,
    }


async def list_policy(db: AsyncSession) -> dict:
    state = await _state(db)
    rows = (await db.execute(
        select(ModerationLexiconRevision).order_by(ModerationLexiconRevision.revision.desc()).limit(25)
    )).scalars().all()
    active = next((row for row in rows if row.revision == state.active_revision), None)
    if state.active_revision and active is None:
        active = await db.get(ModerationLexiconRevision, state.active_revision)
    return {
        "active_revision": state.active_revision,
        "mode": state.mode,
        "enforced": False,
        "active_rules": active.rules if active else [],
        "revisions": [
            {k: v for k, v in _revision_projection(row).items() if k != "rules"}
            for row in rows
        ],
    }


async def get_revision(db: AsyncSession, revision: int) -> dict:
    if revision == 0:
        return {"revision": 0, "rules": [], "reason": "Пустой словарь", "created_at": None}
    row = await db.get(ModerationLexiconRevision, revision)
    if row is None:
        raise _missing_revision()
    return _revision_projection(row)


async def create_revision(db: AsyncSession, actor_uid, payload: LexiconRevisionCreate) -> dict:
    state = await _state(db, lock=True)
    previous = (await db.execute(
        select(func.max(ModerationLexiconRevision.revision))
    )).scalar_one() or 0
    row = ModerationLexiconRevision(
        revision=previous + 1, rules=[rule.model_dump(mode="json") for rule in payload.rules],
        reason=payload.reason, created_by_account_uid=actor_uid,
    )
    db.add(row)
    await db.flush()
    db.add(ModerationLexiconAudit(
        actor_account_uid=actor_uid, action="draft_created",
        previous_revision=state.active_revision, next_revision=state.active_revision,
        previous_mode=state.mode, next_mode=state.mode,
        reason=f"draft={row.revision}; {payload.reason}",
    ))
    await db.commit()
    await db.refresh(row)
    return _revision_projection(row)


async def activate_revision(db: AsyncSession, actor_uid, payload: LexiconActivate) -> dict:
    state = await _state(db, lock=True)
    if payload.revision and await db.get(ModerationLexiconRevision, payload.revision) is None:
        raise _missing_revision()
    previous_revision, previous_mode = state.active_revision, state.mode
    state.active_revision = payload.revision
    state.mode = payload.mode
    state.updated_by_account_uid = actor_uid
    state.updated_at = datetime.utcnow()
    db.add(ModerationLexiconAudit(
        actor_account_uid=actor_uid, action="activated" if payload.mode == "shadow" else "disabled",
        previous_revision=previous_revision, next_revision=payload.revision,
        previous_mode=previous_mode, next_mode=payload.mode, reason=payload.reason,
    ))
    await db.commit()
    return {"revision": payload.revision, "mode": payload.mode, "enforced": False}


async def simulate_policy(db: AsyncSession, text: str, revision: int | None = None, rules: list | None = None) -> dict:
    state = await _state(db)
    revision = state.active_revision if revision is None else revision
    row = await db.get(ModerationLexiconRevision, revision) if revision else None
    if revision and row is None:
        raise _missing_revision()
    selected = [rule.model_dump(mode="json") for rule in rules] if rules is not None else (row.rules if row else [])
    return simulate_rules(text, selected, revision=revision, mode=state.mode)


async def policy_audit(db: AsyncSession, limit: int = 50) -> list[dict]:
    rows = (await db.execute(
        select(ModerationLexiconAudit).order_by(ModerationLexiconAudit.uid.desc()).limit(limit)
    )).scalars().all()
    return [{
        "uid": x.uid, "action": x.action, "previous_revision": x.previous_revision,
        "next_revision": x.next_revision, "previous_mode": x.previous_mode,
        "next_mode": x.next_mode, "reason": x.reason,
        "actor_account_uid": str(x.actor_account_uid) if x.actor_account_uid else None,
        "created_at": x.created_at.isoformat(),
    } for x in rows]
