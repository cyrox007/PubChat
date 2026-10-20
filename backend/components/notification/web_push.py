from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from uuid import UUID, uuid4

from pywebpush import WebPushException, webpush
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from components.identity.model import Account
from components.notification.model import (
    ExternalDeliveryLedger,
    MessageNotificationPreference,
    WebPushSubscription,
)
from components.notification.schemas import WebPushSubscriptionUpsertRequest
from components.notification.unread_dm_email import _eligible_unread_summary, utc_naive
from components.notification.space_reply_delivery import space_reply_claim_payload
from components.realtime import realtime_service
from settings import config
from utils.logger import setup_logger


logger = setup_logger(__name__)
DELIVERY_CHANNEL_WEB_PUSH = "web_push"
DEFAULT_PUSH_PATH = "/messenger"


@dataclass(frozen=True)
class PushSubscriptionTarget:
    uid: UUID
    endpoint: str
    p256dh: str
    auth: str


@dataclass(frozen=True)
class PushDeliveryClaim:
    uid: UUID
    account_uid: UUID
    token: str
    attempt_count: int
    aggregate_key: str


@dataclass
class PushDeliveryStats:
    infrastructure_ready: bool = False
    claimed: int = 0
    delivered: int = 0
    retried: int = 0
    failed: int = 0
    suppressed: int = 0
    terminal_subscriptions_removed: int = 0


class WebPushProviderError(RuntimeError):
    def __init__(self, failure_class: str, *, retryable: bool, terminal_subscription: bool = False) -> None:
        super().__init__(failure_class)
        self.failure_class = failure_class
        self.retryable = retryable
        self.terminal_subscription = terminal_subscription


def endpoint_fingerprint(endpoint: str) -> str:
    return hashlib.sha256(endpoint.encode("utf-8")).hexdigest()


def normalize_push_endpoint(endpoint: str) -> str:
    normalized = str(endpoint or "").strip()
    parsed = urlparse(normalized)
    if parsed.scheme == "https" and parsed.netloc:
        return normalized
    if config.DEBUG and parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}:
        return normalized
    raise ValueError("invalid_push_endpoint")


def push_cooldown_slot(now: datetime) -> int:
    current = utc_naive(now).replace(tzinfo=timezone.utc)
    return int(current.timestamp()) // config.WEB_PUSH_CONVERSATION_COOLDOWN_SECONDS


def push_retry_delay_seconds(attempt_count: int) -> int:
    exponent = max(0, int(attempt_count) - 1)
    raw = config.WEB_PUSH_DELIVERY_RETRY_BASE_SECONDS * (2**min(exponent, 10))
    return min(raw, config.WEB_PUSH_DELIVERY_RETRY_MAX_SECONDS)


def build_messenger_push_payload() -> dict:
    return {
        "type": "messenger",
        "title": "Новое сообщение в PubChat",
        "body": "У вас есть новое личное сообщение.",
        "url": DEFAULT_PUSH_PATH,
        "tag": "pubchat-messenger",
    }


def classify_web_push_exception(exc: WebPushException) -> WebPushProviderError:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if status_code is None:
        status_code = getattr(response, "status", None)
    try:
        code = int(status_code) if status_code is not None else 0
    except (TypeError, ValueError):
        code = 0

    if code in {404, 410}:
        return WebPushProviderError(
            f"push_{code}",
            retryable=False,
            terminal_subscription=True,
        )
    if code in {408, 425, 429} or code >= 500:
        return WebPushProviderError(f"push_{code or 'unavailable'}", retryable=True)
    if code:
        return WebPushProviderError(f"push_{code}", retryable=False)
    return WebPushProviderError("push_provider_error", retryable=True)


class WebPushProvider:
    @property
    def configured(self) -> bool:
        return config.web_push_configured()

    async def send(self, target: PushSubscriptionTarget, payload: dict) -> None:
        if not self.configured:
            raise WebPushProviderError("web_push_not_configured", retryable=False)

        subscription_info = {
            "endpoint": target.endpoint,
            "keys": {"p256dh": target.p256dh, "auth": target.auth},
        }
        try:
            await asyncio.to_thread(
                webpush,
                subscription_info=subscription_info,
                data=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                vapid_private_key=config.WEB_PUSH_VAPID_PRIVATE_KEY,
                vapid_claims={"sub": config.WEB_PUSH_VAPID_SUBJECT},
                ttl=config.WEB_PUSH_TTL_SECONDS,
                timeout=10,
            )
        except WebPushException as exc:
            raise classify_web_push_exception(exc) from exc
        except Exception as exc:
            raise WebPushProviderError("push_transport_error", retryable=True) from exc


async def resolve_account_uid_for_legacy_user(db: AsyncSession, legacy_user_uid: UUID) -> UUID | None:
    result = await db.execute(
        select(Account.uid)
        .where(
            Account.legacy_user_uid == legacy_user_uid,
            Account.status == "active",
            Account.deleted_at.is_(None),
        )
        .limit(1)
    )
    return result.scalar_one_or_none()


async def upsert_web_push_subscription(
    db: AsyncSession,
    account_uid: UUID,
    payload: WebPushSubscriptionUpsertRequest,
    *,
    user_agent: str | None,
) -> dict:
    endpoint = normalize_push_endpoint(payload.endpoint)
    digest = endpoint_fingerprint(endpoint)
    current = datetime.utcnow()
    result = await db.execute(
        select(WebPushSubscription).where(WebPushSubscription.endpoint_hash == digest).limit(1)
    )
    item = result.scalar_one_or_none()
    if item is None:
        item = WebPushSubscription(
            account_uid=account_uid,
            endpoint=endpoint,
            endpoint_hash=digest,
            p256dh=payload.keys.p256dh,
            auth=payload.keys.auth,
            user_agent=(user_agent or "")[:500] or None,
            created_at=current,
            updated_at=current,
            last_seen_at=current,
        )
        db.add(item)
    else:
        # A browser subscription belongs to the most recently authenticated
        # Account using it, preventing old-account delivery after logout/login.
        item.account_uid = account_uid
        item.endpoint = endpoint
        item.p256dh = payload.keys.p256dh
        item.auth = payload.keys.auth
        item.user_agent = (user_agent or "")[:500] or None
        item.updated_at = current
        item.last_seen_at = current

    await db.commit()
    await db.refresh(item)
    return {"uid": str(item.uid), "registered": True}


async def remove_web_push_subscription(
    db: AsyncSession,
    account_uid: UUID,
    endpoint: str,
) -> bool:
    try:
        normalized = normalize_push_endpoint(endpoint)
    except ValueError:
        return False
    digest = endpoint_fingerprint(normalized)
    result = await db.execute(
        delete(WebPushSubscription)
        .where(
            WebPushSubscription.account_uid == account_uid,
            WebPushSubscription.endpoint_hash == digest,
        )
        .returning(WebPushSubscription.uid)
    )
    removed = result.scalar_one_or_none() is not None
    await db.commit()
    return removed


async def web_push_subscription_count(db: AsyncSession, account_uid: UUID) -> int:
    result = await db.execute(
        select(WebPushSubscription.uid).where(WebPushSubscription.account_uid == account_uid)
    )
    return len(result.all())


async def queue_messenger_web_push(
    db: AsyncSession,
    *,
    receiver_legacy_uid: UUID,
    sender_legacy_uid: UUID,
    now: datetime | None = None,
) -> bool:
    if not config.web_push_configured():
        return False

    account_uid = await resolve_account_uid_for_legacy_user(db, receiver_legacy_uid)
    if account_uid is None:
        return False
    preference = await db.get(MessageNotificationPreference, account_uid)
    if not preference or not preference.web_push_messenger:
        return False

    subscription = await db.execute(
        select(WebPushSubscription.uid)
        .where(WebPushSubscription.account_uid == account_uid)
        .limit(1)
    )
    if subscription.scalar_one_or_none() is None:
        return False

    current = utc_naive(now or datetime.now(timezone.utc))
    aggregate_key = f"messenger:{sender_legacy_uid}"
    cutoff = current - timedelta(seconds=config.WEB_PUSH_CONVERSATION_COOLDOWN_SECONDS)
    recent = await db.execute(
        select(ExternalDeliveryLedger.uid)
        .where(
            ExternalDeliveryLedger.account_uid == account_uid,
            ExternalDeliveryLedger.channel == DELIVERY_CHANNEL_WEB_PUSH,
            ExternalDeliveryLedger.aggregate_key == aggregate_key,
            ExternalDeliveryLedger.created_at >= cutoff,
            ExternalDeliveryLedger.status != "suppressed",
        )
        .limit(1)
    )
    if recent.scalar_one_or_none() is not None:
        return False

    dedupe_key = f"{aggregate_key}:slot:{push_cooldown_slot(current)}"
    statement = (
        insert(ExternalDeliveryLedger)
        .values(
            account_uid=account_uid,
            channel=DELIVERY_CHANNEL_WEB_PUSH,
            aggregate_key=aggregate_key,
            dedupe_key=dedupe_key,
            status="pending",
            unread_count=1,
            dialog_count=1,
            attempt_count=0,
            next_attempt_at=current,
            created_at=current,
            updated_at=current,
        )
        .on_conflict_do_nothing(constraint="uq_external_delivery_dedupe")
        .returning(ExternalDeliveryLedger.uid)
    )
    queued = (await db.execute(statement)).scalar_one_or_none() is not None
    await db.commit()
    return queued


async def _claim_one(db: AsyncSession, now: datetime) -> PushDeliveryClaim | None:
    current = utc_naive(now)
    pending = and_(
        ExternalDeliveryLedger.status == "pending",
        or_(
            ExternalDeliveryLedger.next_attempt_at.is_(None),
            ExternalDeliveryLedger.next_attempt_at <= current,
        ),
    )
    expired = and_(
        ExternalDeliveryLedger.status == "processing",
        or_(
            ExternalDeliveryLedger.claim_expires_at.is_(None),
            ExternalDeliveryLedger.claim_expires_at <= current,
        ),
    )
    result = await db.execute(
        select(ExternalDeliveryLedger)
        .where(
            ExternalDeliveryLedger.channel == DELIVERY_CHANNEL_WEB_PUSH,
            or_(pending, expired),
        )
        .order_by(ExternalDeliveryLedger.next_attempt_at.asc().nullsfirst(), ExternalDeliveryLedger.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if row is None:
        await db.rollback()
        return None

    token = uuid4().hex
    row.status = "processing"
    row.claim_token = token
    row.claim_expires_at = current + timedelta(seconds=config.WEB_PUSH_DELIVERY_LEASE_SECONDS)
    row.attempt_count = int(row.attempt_count or 0) + 1
    row.attempted_at = current
    row.updated_at = current
    claim = PushDeliveryClaim(
        uid=UUID(str(row.uid)),
        account_uid=UUID(str(row.account_uid)),
        token=token,
        attempt_count=row.attempt_count,
        aggregate_key=row.aggregate_key,
    )
    await db.commit()
    return claim


async def _claimed_row(db: AsyncSession, claim: PushDeliveryClaim) -> ExternalDeliveryLedger | None:
    result = await db.execute(
        select(ExternalDeliveryLedger)
        .where(
            ExternalDeliveryLedger.uid == claim.uid,
            ExternalDeliveryLedger.status == "processing",
            ExternalDeliveryLedger.claim_token == claim.token,
        )
        .with_for_update()
    )
    return result.scalar_one_or_none()


async def _finish_claim(db: AsyncSession, claim: PushDeliveryClaim, *, status: str, now: datetime, failure: str | None = None) -> None:
    row = await _claimed_row(db, claim)
    if row is None:
        await db.rollback()
        return
    current = utc_naive(now)
    row.status = status
    row.claim_token = None
    row.claim_expires_at = None
    row.updated_at = current
    row.failure_class = failure[:80] if failure else None
    row.next_attempt_at = None
    if status == "delivered":
        row.delivered_at = current
        row.provider_message_id = f"web-push:{claim.uid}"[:180]
    elif status == "failed":
        row.failed_at = current
    await db.commit()


async def _retry_claim(db: AsyncSession, claim: PushDeliveryClaim, *, now: datetime, failure: str) -> bool:
    row = await _claimed_row(db, claim)
    if row is None:
        await db.rollback()
        return False
    current = utc_naive(now)
    exhausted = int(row.attempt_count or 0) >= config.WEB_PUSH_DELIVERY_MAX_ATTEMPTS
    row.claim_token = None
    row.claim_expires_at = None
    row.failure_class = failure[:80]
    row.updated_at = current
    if exhausted:
        row.status = "failed"
        row.failed_at = current
        row.next_attempt_at = None
        await db.commit()
        return False
    row.status = "pending"
    row.next_attempt_at = current + timedelta(seconds=push_retry_delay_seconds(row.attempt_count))
    await db.commit()
    return True


async def _subscription_targets(db: AsyncSession, account_uid: UUID) -> list[PushSubscriptionTarget]:
    result = await db.execute(
        select(WebPushSubscription)
        .where(WebPushSubscription.account_uid == account_uid)
        .order_by(WebPushSubscription.updated_at.desc())
    )
    return [
        PushSubscriptionTarget(
            uid=UUID(str(item.uid)),
            endpoint=item.endpoint,
            p256dh=item.p256dh,
            auth=item.auth,
        )
        for item in result.scalars().all()
    ]


async def _remove_terminal_subscription(session_factory: async_sessionmaker[AsyncSession], uid: UUID) -> None:
    async with session_factory() as db:
        await db.execute(delete(WebPushSubscription).where(WebPushSubscription.uid == uid))
        await db.commit()


async def run_web_push_delivery_worker(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    provider: WebPushProvider | None = None,
    max_deliveries: int | None = None,
    now: datetime | None = None,
) -> PushDeliveryStats:
    current = utc_naive(now or datetime.now(timezone.utc))
    stats = PushDeliveryStats()
    provider = provider or WebPushProvider()
    if not provider.configured:
        logger.error("Web Push delivery skipped: VAPID is not configured")
        return stats

    if not realtime_service.distributed:
        await realtime_service.start()
    if not realtime_service.distributed and not config.DEBUG:
        logger.error("Web Push delivery skipped: distributed Redis presence is unavailable")
        return stats
    stats.infrastructure_ready = True

    limit = max(1, min(int(max_deliveries or config.WEB_PUSH_DELIVERY_BATCH_SIZE), 250))
    for _ in range(limit):
        async with session_factory() as claim_db:
            claim = await _claim_one(claim_db, current)
        if claim is None:
            break
        stats.claimed += 1

        try:
            # A backgrounded tab retains its websocket connection; online
            # presence is NOT evidence that the user is viewing PubChat.
            is_reply = claim.aggregate_key.startswith("space-reply:")
            async with session_factory() as db:
                preference = await db.get(MessageNotificationPreference, claim.account_uid)
                permitted = preference and (
                    preference.web_push_space if is_reply else preference.web_push_messenger
                )
                payload_for_claim = (
                    await space_reply_claim_payload(db, claim.aggregate_key, claim.account_uid)
                    if is_reply else
                    (build_messenger_push_payload()
                     if await _eligible_unread_summary(db, claim.account_uid) is not None else None)
                )
                if not permitted or payload_for_claim is None:
                    await _finish_claim(db, claim, status="suppressed", now=current, failure="push_opt_out_or_event_read")
                    stats.suppressed += 1
                    continue
                targets = await _subscription_targets(db, claim.account_uid)

            if not targets:
                async with session_factory() as db:
                    await _finish_claim(db, claim, status="suppressed", now=current, failure="no_active_subscription")
                stats.suppressed += 1
                continue

            delivered = 0
            retryable_failure = False
            last_failure = "push_delivery_failed"
            for target in targets:
                try:
                    await provider.send(target, payload_for_claim)
                    delivered += 1
                except WebPushProviderError as exc:
                    last_failure = exc.failure_class
                    if exc.terminal_subscription:
                        await _remove_terminal_subscription(session_factory, target.uid)
                        stats.terminal_subscriptions_removed += 1
                    elif exc.retryable:
                        retryable_failure = True

            if delivered:
                async with session_factory() as db:
                    await _finish_claim(db, claim, status="delivered", now=current)
                stats.delivered += 1
            elif retryable_failure:
                async with session_factory() as db:
                    retrying = await _retry_claim(db, claim, now=current, failure=last_failure)
                stats.retried += int(retrying)
                stats.failed += int(not retrying)
            else:
                async with session_factory() as db:
                    await _finish_claim(db, claim, status="suppressed", now=current, failure=last_failure)
                stats.suppressed += 1
        except Exception:
            logger.exception("Web Push delivery claim failed: delivery=%s", claim.uid)
            async with session_factory() as db:
                retrying = await _retry_claim(db, claim, now=current, failure="push_worker_error")
            stats.retried += int(retrying)
            stats.failed += int(not retrying)

    return stats
