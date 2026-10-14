from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from components.identity.model import Account
from components.message.model import Message, PrivateMessage
from components.moderation.abuse_model import TrustSafetyAbuseSignal
from components.reputation.model import AccountReputationAssessment
from components.reputation.schemas import ReputationAIAssessment
from components.reputation.settings import reputation_ai_config
from components.room.model import Room
from components.space.model import SpaceMembership


AI_SCHEMA_VERSION = "v1"
AI_PROVIDER_DISABLED = "disabled"
AI_PROVIDER_HTTP_JSON = "http_json"


class ReputationAIProviderError(RuntimeError):
    pass


class ReputationAIProvider(Protocol):
    key: str
    model_name: str | None

    async def assess(self, payload: dict) -> ReputationAIAssessment:
        ...


@dataclass(slots=True)
class DisabledReputationAIProvider:
    key: str = AI_PROVIDER_DISABLED
    model_name: str | None = None

    async def assess(self, payload: dict) -> ReputationAIAssessment:
        raise ReputationAIProviderError("reputation AI provider is disabled")


@dataclass(slots=True)
class HttpJsonReputationAIProvider:
    endpoint: str
    api_key: str = ""
    model_name: str | None = None
    timeout_seconds: float = 15.0
    key: str = AI_PROVIDER_HTTP_JSON

    def _request_sync(self, payload: dict) -> dict:
        body = json.dumps(
            {
                "task": "pubchat_reputation_assessment",
                "schema_version": AI_SCHEMA_VERSION,
                "model": self.model_name,
                "input": payload,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "PubChat-Reputation-AI/1.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(self.endpoint, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read(256 * 1024)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            raise ReputationAIProviderError("reputation AI provider request failed") from exc

        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ReputationAIProviderError("reputation AI provider returned invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise ReputationAIProviderError("reputation AI provider returned invalid envelope")
        assessment = parsed.get("assessment", parsed)
        if not isinstance(assessment, dict):
            raise ReputationAIProviderError("reputation AI provider returned invalid assessment")
        return assessment

    async def assess(self, payload: dict) -> ReputationAIAssessment:
        raw = await asyncio.to_thread(self._request_sync, payload)
        try:
            return ReputationAIAssessment.model_validate(raw)
        except ValidationError as exc:
            raise ReputationAIProviderError("reputation AI response failed schema validation") from exc


def build_reputation_ai_provider() -> ReputationAIProvider:
    provider = reputation_ai_config.provider
    if provider in {"", AI_PROVIDER_DISABLED}:
        return DisabledReputationAIProvider()
    if provider == AI_PROVIDER_HTTP_JSON:
        if not reputation_ai_config.configured():
            raise ReputationAIProviderError("reputation AI provider configuration is incomplete")
        return HttpJsonReputationAIProvider(
            endpoint=reputation_ai_config.endpoint,
            api_key=reputation_ai_config.api_key,
            model_name=reputation_ai_config.model or None,
            timeout_seconds=reputation_ai_config.timeout_seconds,
        )
    raise ReputationAIProviderError("unsupported reputation AI provider")


async def _behavior_payload(db: AsyncSession, account: Account) -> dict:
    """Build privacy-minimal behavioral features for the trained reputation model.

    The application deliberately does not calculate reputation from these counters.
    They are model features only. Message text, handles and profile content are not
    included in the reputation request.
    """
    now = datetime.utcnow()
    window_start = now - timedelta(days=reputation_ai_config.behavior_window_days)
    legacy_uid = account.legacy_user_uid

    space_message_count = 0
    dm_sent_count = 0
    active_space_days = 0
    spaces_participated = 0
    if legacy_uid:
        space_message_count = int(
            (
                await db.execute(
                    select(func.count(Message.uid)).where(
                        Message.author_uid == legacy_uid,
                        Message.created_at >= window_start,
                    )
                )
            ).scalar_one()
            or 0
        )
        dm_sent_count = int(
            (
                await db.execute(
                    select(func.count(PrivateMessage.id)).where(
                        PrivateMessage.sender_uid == legacy_uid,
                        PrivateMessage.created_at >= window_start,
                    )
                )
            ).scalar_one()
            or 0
        )
        active_space_days = int(
            (
                await db.execute(
                    select(func.count(func.distinct(func.date(Message.created_at)))).where(
                        Message.author_uid == legacy_uid,
                        Message.created_at >= window_start,
                    )
                )
            ).scalar_one()
            or 0
        )

    spaces_participated = int(
        (
            await db.execute(
                select(func.count(func.distinct(SpaceMembership.room_uid))).where(
                    SpaceMembership.account_uid == account.uid,
                    SpaceMembership.status == "active",
                )
            )
        ).scalar_one()
        or 0
    )

    abuse_rows = (
        await db.execute(
            select(
                TrustSafetyAbuseSignal.severity,
                TrustSafetyAbuseSignal.status,
                func.count(TrustSafetyAbuseSignal.uid),
            )
            .where(
                TrustSafetyAbuseSignal.account_uid == account.uid,
                TrustSafetyAbuseSignal.last_seen_at >= window_start,
            )
            .group_by(TrustSafetyAbuseSignal.severity, TrustSafetyAbuseSignal.status)
        )
    ).all()
    abuse_signals = [
        {"severity": severity, "status": signal_status, "count": int(count)}
        for severity, signal_status, count in abuse_rows
    ]

    owned_active_spaces = int(
        (
            await db.execute(
                select(func.count(Room.uid)).where(
                    Room.owner_uid == account.legacy_user_uid,
                    Room.is_active.is_(True),
                )
            )
        ).scalar_one()
        or 0
    ) if account.legacy_user_uid else 0

    account_age_days = max(0, (now - account.created_at).days) if account.created_at else 0
    return {
        "account": {
            "age_days": account_age_days,
            "trust_level": account.trust_level,
            "status": account.status,
        },
        "window_days": reputation_ai_config.behavior_window_days,
        "behavior": {
            "space_messages": space_message_count,
            "dm_messages_sent": dm_sent_count,
            "active_space_days": active_space_days,
            "spaces_participated": spaces_participated,
            "owned_active_spaces": owned_active_spaces,
            "abuse_signals": abuse_signals,
        },
        "policy": {
            "purpose": "earned_privileges",
            "requested_privilege": "space.create",
            "money_must_not_affect_reputation": True,
            "persona_count_must_not_multiply_reputation": True,
            "avoid_raw_activity_as_direct_score": True,
        },
    }


async def get_current_reputation_assessment(
    db: AsyncSession,
    account_uid: UUID,
) -> AccountReputationAssessment | None:
    now = datetime.utcnow()
    result = await db.execute(
        select(AccountReputationAssessment)
        .where(
            AccountReputationAssessment.account_uid == account_uid,
            AccountReputationAssessment.valid_until > now,
        )
        .order_by(AccountReputationAssessment.assessed_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def assess_account_reputation(
    db: AsyncSession,
    account: Account,
    *,
    provider: ReputationAIProvider | None = None,
) -> AccountReputationAssessment:
    try:
        provider = provider or build_reputation_ai_provider()
    except ReputationAIProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error_type": "reputation_ai_not_configured"},
        ) from exc
    if provider.key == AI_PROVIDER_DISABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error_type": "reputation_ai_not_configured"},
        )

    payload = await _behavior_payload(db, account)
    try:
        assessment = await provider.assess(payload)
    except ReputationAIProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error_type": "reputation_ai_provider_unavailable"},
        ) from exc

    now = datetime.utcnow()
    item = AccountReputationAssessment(
        account_uid=account.uid,
        provider_key=provider.key,
        model_name=provider.model_name,
        schema_version=AI_SCHEMA_VERSION,
        overall_label=assessment.overall_label,
        confidence_percent=assessment.confidence_percent,
        dimensions=assessment.dimensions,
        space_creation_eligible=assessment.space_creation_eligible,
        max_owned_active_spaces=assessment.max_owned_active_spaces,
        rationale=assessment.rationale,
        behavior_window_days=reputation_ai_config.behavior_window_days,
        assessed_at=now,
        valid_until=now + timedelta(hours=reputation_ai_config.assessment_ttl_hours),
    )
    db.add(item)
    await db.flush()
    return item


async def ensure_space_creation_privilege(
    db: AsyncSession,
    account: Account,
) -> AccountReputationAssessment | None:
    """Require an earned Account-level privilege before creating a Space.

    In required mode there is no points fallback: if the trained model cannot make
    a valid assessment, creation fails closed. Shadow mode exists only for staged
    rollout and never fabricates a reputation score.
    """
    assessment = await get_current_reputation_assessment(db, account.uid)
    if assessment is None:
        try:
            assessment = await assess_account_reputation(db, account)
        except HTTPException:
            if reputation_ai_config.enforcement_mode == "shadow":
                return None
            raise

    if reputation_ai_config.enforcement_mode == "shadow":
        return assessment

    if not assessment.space_creation_eligible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_type": "space_creation_privilege_required",
                "reputation_label": assessment.overall_label,
                "assessment_valid_until": assessment.valid_until.isoformat(),
            },
        )

    owned_active_spaces = 0
    if account.legacy_user_uid:
        owned_active_spaces = int(
            (
                await db.execute(
                    select(func.count(Room.uid)).where(
                        Room.owner_uid == account.legacy_user_uid,
                        Room.is_active.is_(True),
                    )
                )
            ).scalar_one()
            or 0
        )
    if owned_active_spaces >= assessment.max_owned_active_spaces:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error_type": "space_creation_limit_reached",
                "owned_active_spaces": owned_active_spaces,
                "max_owned_active_spaces": assessment.max_owned_active_spaces,
            },
        )
    return assessment


def reputation_projection(item: AccountReputationAssessment | None) -> dict:
    if item is None:
        return {
            "status": "unassessed",
            "overall_label": "unknown",
            "dimensions": {},
            "space_creation_eligible": False,
            "max_owned_active_spaces": 0,
            "valid_until": None,
        }
    return {
        "status": "assessed",
        "overall_label": item.overall_label,
        "confidence_percent": item.confidence_percent,
        "dimensions": item.dimensions or {},
        "space_creation_eligible": item.space_creation_eligible,
        "max_owned_active_spaces": item.max_owned_active_spaces,
        "rationale": item.rationale,
        "model": item.model_name,
        "assessed_at": item.assessed_at.isoformat(),
        "valid_until": item.valid_until.isoformat(),
    }
