from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from components.notification.model import ExternalDeliveryLedger, MessageNotificationPreference, NativePushDevice, NativePushDeliveryReceipt
from components.notification.schemas import NativePushDeviceUpsertRequest
from components.notification.unread_dm_email import _eligible_unread_summary, utc_naive
from components.notification.space_reply_delivery import space_reply_claim_payload
from components.realtime import realtime_service
from utils.logger import setup_logger


logger = setup_logger(__name__)
DELIVERY_CHANNEL_NATIVE_PUSH = "native_push"
DEFAULT_PUSH_PATH = "/messenger"
FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
FCM_TOKEN_URL = "https://oauth2.googleapis.com/token"

NATIVE_PUSH_MAX_ATTEMPTS = max(1, int(os.getenv("NATIVE_PUSH_DELIVERY_MAX_ATTEMPTS", "5")))
NATIVE_PUSH_RETRY_BASE_SECONDS = max(30, int(os.getenv("NATIVE_PUSH_DELIVERY_RETRY_BASE_SECONDS", "60")))
NATIVE_PUSH_RETRY_MAX_SECONDS = max(NATIVE_PUSH_RETRY_BASE_SECONDS, int(os.getenv("NATIVE_PUSH_DELIVERY_RETRY_MAX_SECONDS", "1800")))
NATIVE_PUSH_LEASE_SECONDS = max(60, int(os.getenv("NATIVE_PUSH_DELIVERY_LEASE_SECONDS", "180")))
NATIVE_PUSH_BATCH_SIZE = max(1, min(250, int(os.getenv("NATIVE_PUSH_DELIVERY_BATCH_SIZE", "50"))))
NATIVE_PUSH_COOLDOWN_SECONDS = max(30, int(os.getenv("NATIVE_PUSH_CONVERSATION_COOLDOWN_SECONDS", "90")))


def _fcm_project_id() -> str:
    return os.getenv("FCM_PROJECT_ID", "").strip()


def _fcm_service_account_email() -> str:
    return os.getenv("FCM_SERVICE_ACCOUNT_EMAIL", "").strip()


def _fcm_private_key() -> str:
    return os.getenv("FCM_SERVICE_ACCOUNT_PRIVATE_KEY", "").replace("\\n", "\n").strip()


def fcm_configured() -> bool:
    return bool(_fcm_project_id() and _fcm_service_account_email() and _fcm_private_key())


def token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def build_messenger_native_push_payload() -> dict[str, str]:
    # Deliberately generic. E2EE plaintext, sender names, file names and message
    # excerpts are not available to this delivery adapter and never belong here.
    return {
        "type": "messenger",
        "title": "Новое сообщение в PubChat",
        "body": "У вас есть новое личное сообщение.",
        "url": DEFAULT_PUSH_PATH,
        "tag": "pubchat-messenger",
    }


def native_push_retry_delay_seconds(attempt_count: int) -> int:
    exponent = max(0, int(attempt_count) - 1)
    return min(NATIVE_PUSH_RETRY_BASE_SECONDS * (2 ** min(exponent, 10)), NATIVE_PUSH_RETRY_MAX_SECONDS)


def native_unread_dedupe_key(latest_uid: UUID) -> str:
    """One OS alert per unread message, independent of cooldown timestamps."""
    return f"unread-dm:{latest_uid}"


def _cooldown_slot(now: datetime) -> int:
    current = utc_naive(now).replace(tzinfo=timezone.utc)
    return int(current.timestamp()) // NATIVE_PUSH_COOLDOWN_SECONDS


@dataclass(frozen=True)
class NativePushTarget:
    uid: UUID
    token: str
    provider: str
    platform: str


@dataclass(frozen=True)
class NativePushClaim:
    uid: UUID
    account_uid: UUID
    token: str
    attempt_count: int
    aggregate_key: str


@dataclass
class NativePushStats:
    infrastructure_ready: bool = False
    accounts_scanned: int = 0
    queued: int = 0
    claimed: int = 0
    delivered: int = 0
    retried: int = 0
    failed: int = 0
    suppressed: int = 0
    terminal_devices_revoked: int = 0


class NativePushProviderError(RuntimeError):
    def __init__(self, failure_class: str, *, retryable: bool, terminal_device: bool = False) -> None:
        super().__init__(failure_class)
        self.failure_class = failure_class
        self.retryable = retryable
        self.terminal_device = terminal_device


def _provider_projection(item: NativePushDevice) -> dict:
    return {
        "uid": str(item.uid),
        "installation_uid": str(item.installation_uid),
        "platform": item.platform,
        "provider": item.provider,
        "device_label": item.device_label,
        "app_version": item.app_version,
        "last_seen_at": item.last_seen_at.isoformat() if item.last_seen_at else None,
        "revoked_at": item.revoked_at.isoformat() if item.revoked_at else None,
    }


async def upsert_native_push_device(db: AsyncSession, account_uid: UUID, payload: NativePushDeviceUpsertRequest) -> dict:
    if payload.platform == "android" and payload.provider != "fcm":
        raise ValueError("android_requires_fcm")
    if payload.platform == "ios" and payload.provider != "apns":
        raise ValueError("ios_requires_apns")

    current = datetime.utcnow()
    digest = token_fingerprint(payload.token)
    result = await db.execute(
        select(NativePushDevice).where(
            or_(
                NativePushDevice.installation_uid == payload.installation_uid,
                NativePushDevice.token_hash == digest,
            )
        ).limit(1)
    )
    item = result.scalar_one_or_none()
    if item is None:
        item = NativePushDevice(
            account_uid=account_uid,
            installation_uid=payload.installation_uid,
            platform=payload.platform,
            provider=payload.provider,
            token=payload.token,
            token_hash=digest,
            device_label=payload.device_label,
            app_version=payload.app_version,
            created_at=current,
            updated_at=current,
            last_seen_at=current,
        )
        db.add(item)
    else:
        # An installation/token follows the most recently authenticated Account,
        # preventing delivery to the previous Account after sign-out/sign-in.
        item.account_uid = account_uid
        item.installation_uid = payload.installation_uid
        item.platform = payload.platform
        item.provider = payload.provider
        item.token = payload.token
        item.token_hash = digest
        item.device_label = payload.device_label
        item.app_version = payload.app_version
        item.updated_at = current
        item.last_seen_at = current
        item.revoked_at = None

    await db.commit()
    await db.refresh(item)
    return _provider_projection(item)


async def list_native_push_devices(db: AsyncSession, account_uid: UUID) -> list[dict]:
    result = await db.execute(
        select(NativePushDevice)
        .where(NativePushDevice.account_uid == account_uid)
        .order_by(NativePushDevice.updated_at.desc())
    )
    return [_provider_projection(item) for item in result.scalars().all()]


async def revoke_native_push_device(db: AsyncSession, account_uid: UUID, installation_uid: UUID) -> bool:
    result = await db.execute(
        select(NativePushDevice).where(
            NativePushDevice.account_uid == account_uid,
            NativePushDevice.installation_uid == installation_uid,
        ).limit(1)
    )
    item = result.scalar_one_or_none()
    if item is None:
        return False
    if item.revoked_at is None:
        item.revoked_at = datetime.utcnow()
        item.updated_at = datetime.utcnow()
        await db.commit()
    return True


class FCMProvider:
    def __init__(self) -> None:
        self._access_token: str | None = None
        self._access_token_expires_at = 0

    @property
    def configured(self) -> bool:
        from components.notification.apns_push import apns_configured
        return fcm_configured() or apns_configured()

    def _oauth_token_sync(self) -> str:
        now = int(time.time())
        if self._access_token and now < self._access_token_expires_at - 60:
            return self._access_token
        assertion = jwt.encode(
            {
                "iss": _fcm_service_account_email(),
                "scope": FCM_SCOPE,
                "aud": FCM_TOKEN_URL,
                "iat": now,
                "exp": now + 3600,
            },
            _fcm_private_key(),
            algorithm="RS256",
        )
        body = urllib.parse.urlencode(
            {
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            FCM_TOKEN_URL,
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            raise NativePushProviderError("fcm_oauth_unavailable", retryable=True) from exc
        token = str(payload.get("access_token") or "")
        if not token:
            raise NativePushProviderError("fcm_oauth_invalid_response", retryable=True)
        self._access_token = token
        self._access_token_expires_at = now + int(payload.get("expires_in") or 3600)
        return token

    @staticmethod
    def _classify_http_error(exc: urllib.error.HTTPError) -> NativePushProviderError:
        code = int(exc.code or 0)
        try:
            body = json.loads(exc.read().decode("utf-8"))
        except Exception:
            body = {}
        text = json.dumps(body, ensure_ascii=False).upper()
        if code in {404, 410} or "UNREGISTERED" in text:
            return NativePushProviderError("fcm_unregistered", retryable=False, terminal_device=True)
        if code == 400 and ("INVALID_ARGUMENT" in text or "INVALID REGISTRATION" in text):
            return NativePushProviderError("fcm_invalid_token", retryable=False, terminal_device=True)
        if code in {408, 425, 429} or code >= 500:
            return NativePushProviderError(f"fcm_{code or 'unavailable'}", retryable=True)
        if code in {401, 403}:
            return NativePushProviderError(f"fcm_auth_{code}", retryable=True)
        return NativePushProviderError(f"fcm_{code or 'provider_error'}", retryable=False)

    def _send_sync(self, target: NativePushTarget, payload: dict[str, str]) -> str:
        if target.provider != "fcm":
            raise NativePushProviderError("native_provider_not_implemented", retryable=False)
        if not self.configured:
            raise NativePushProviderError("fcm_not_configured", retryable=False)
        access_token = self._oauth_token_sync()
        endpoint = f"https://fcm.googleapis.com/v1/projects/{urllib.parse.quote(_fcm_project_id(), safe='')}/messages:send"
        message = {
            "message": {
                "token": target.token,
                "notification": {"title": payload["title"], "body": payload["body"]},
                "data": {key: str(value) for key, value in payload.items() if key not in {"title", "body"}},
                "android": {
                    "priority": "high",
                    "notification": {
                        "tag": payload.get("tag", "pubchat"),
                        "channel_id": ("pubchat_space_replies_chime_v2" if payload.get("type") == "space_reply" else "pubchat_messages_chime_v2"),
                    },
                },
            }
        }
        if payload.get("type") == "call":
            # Android must receive call data in FirebaseMessagingService so it
            # can build notification actions. A mixed notification+data FCM
            # message bypasses onMessageReceived() in the background.
            # Only generic text and call_uid are delivered, never SDP/ICE.
            message["message"].pop("notification", None)
            message["message"]["data"] = {
                key: str(value) for key, value in payload.items()
                if key in {"type", "call_uid", "title", "body", "tag"}
            }
            message["message"]["android"].pop("notification", None)
            message["message"]["android"]["ttl"] = "60s"
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(message, separators=(",", ":")).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise self._classify_http_error(exc) from exc
        except Exception as exc:
            raise NativePushProviderError("fcm_transport_error", retryable=True) from exc
        return str(response_payload.get("name") or "")[:180]

    async def send(self, target: NativePushTarget, payload: dict[str, str]) -> str:
        if target.provider == "apns" and target.platform == "ios":
            from components.notification.apns_push import apns_provider
            return await apns_provider.send(target, payload)
        return await asyncio.to_thread(self._send_sync, target, payload)


async def _candidate_accounts(db: AsyncSession, limit: int) -> list[UUID]:
    result = await db.execute(
        select(NativePushDevice.account_uid)
        .join(MessageNotificationPreference, MessageNotificationPreference.account_uid == NativePushDevice.account_uid)
        .where(
            NativePushDevice.revoked_at.is_(None),
            MessageNotificationPreference.native_push_messenger.is_(True),
        )
        .group_by(NativePushDevice.account_uid)
        .order_by(func.max(NativePushDevice.updated_at).desc())
        .limit(limit)
    )
    return [UUID(str(value)) for value in result.scalars().all()]


async def queue_native_push_for_unread(db: AsyncSession, *, now: datetime, limit: int = 250) -> tuple[int, int]:
    current = utc_naive(now)
    accounts = await _candidate_accounts(db, max(1, min(int(limit), 250)))
    queued = 0
    for account_uid in accounts:
        summary = await _eligible_unread_summary(db, account_uid)
        if summary is None:
            continue
        recent = await db.execute(
            select(ExternalDeliveryLedger.uid).where(
                ExternalDeliveryLedger.account_uid == account_uid,
                ExternalDeliveryLedger.channel == DELIVERY_CHANNEL_NATIVE_PUSH,
                ExternalDeliveryLedger.created_at >= current - timedelta(seconds=NATIVE_PUSH_COOLDOWN_SECONDS),
                ExternalDeliveryLedger.status != "suppressed",
            ).limit(1)
        )
        if recent.scalar_one_or_none() is not None:
            continue
        aggregate_key = native_unread_dedupe_key(summary.latest_message_uid)
        # Do not resend the same unread message every 90s after it was delivered.
        dedupe_key = aggregate_key
        statement = (
            insert(ExternalDeliveryLedger)
            .values(
                account_uid=account_uid,
                channel=DELIVERY_CHANNEL_NATIVE_PUSH,
                aggregate_key=aggregate_key,
                dedupe_key=dedupe_key,
                status="pending",
                unread_count=summary.unread_count,
                dialog_count=summary.dialog_count,
                attempt_count=0,
                next_attempt_at=current,
                created_at=current,
                updated_at=current,
            )
            .on_conflict_do_nothing(constraint="uq_external_delivery_dedupe")
            .returning(ExternalDeliveryLedger.uid)
        )
        if (await db.execute(statement)).scalar_one_or_none() is not None:
            queued += 1
    await db.commit()
    return len(accounts), queued


async def _claim_one(db: AsyncSession, now: datetime) -> NativePushClaim | None:
    current = utc_naive(now)
    result = await db.execute(
        select(ExternalDeliveryLedger)
        .where(
            ExternalDeliveryLedger.channel == DELIVERY_CHANNEL_NATIVE_PUSH,
            or_(
                and_(
                    ExternalDeliveryLedger.status == "pending",
                    or_(ExternalDeliveryLedger.next_attempt_at.is_(None), ExternalDeliveryLedger.next_attempt_at <= current),
                ),
                and_(
                    ExternalDeliveryLedger.status == "processing",
                    or_(ExternalDeliveryLedger.claim_expires_at.is_(None), ExternalDeliveryLedger.claim_expires_at <= current),
                ),
            ),
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
    row.claim_expires_at = current + timedelta(seconds=NATIVE_PUSH_LEASE_SECONDS)
    row.attempt_count = int(row.attempt_count or 0) + 1
    row.attempted_at = current
    row.updated_at = current
    claim = NativePushClaim(UUID(str(row.uid)), UUID(str(row.account_uid)), token, row.attempt_count, row.aggregate_key)
    await db.commit()
    return claim


async def _claimed_row(db: AsyncSession, claim: NativePushClaim) -> ExternalDeliveryLedger | None:
    result = await db.execute(
        select(ExternalDeliveryLedger).where(
            ExternalDeliveryLedger.uid == claim.uid,
            ExternalDeliveryLedger.status == "processing",
            ExternalDeliveryLedger.claim_token == claim.token,
        ).with_for_update()
    )
    return result.scalar_one_or_none()


async def _finish(db: AsyncSession, claim: NativePushClaim, *, state: str, now: datetime, failure: str | None = None, provider_id: str | None = None) -> None:
    row = await _claimed_row(db, claim)
    if row is None:
        await db.rollback()
        return
    current = utc_naive(now)
    row.status = state
    row.claim_token = None
    row.claim_expires_at = None
    row.next_attempt_at = None
    row.updated_at = current
    row.failure_class = failure[:80] if failure else None
    if state == "delivered":
        row.delivered_at = current
        row.provider_message_id = (provider_id or f"native-push:{claim.uid}")[:180]
    elif state == "failed":
        row.failed_at = current
    await db.commit()


async def _retry(db: AsyncSession, claim: NativePushClaim, *, now: datetime, failure: str) -> bool:
    row = await _claimed_row(db, claim)
    if row is None:
        await db.rollback()
        return False
    current = utc_naive(now)
    row.claim_token = None
    row.claim_expires_at = None
    row.failure_class = failure[:80]
    row.updated_at = current
    if int(row.attempt_count or 0) >= NATIVE_PUSH_MAX_ATTEMPTS:
        row.status = "failed"
        row.failed_at = current
        row.next_attempt_at = None
        await db.commit()
        return False
    row.status = "pending"
    row.next_attempt_at = current + timedelta(seconds=native_push_retry_delay_seconds(row.attempt_count))
    await db.commit()
    return True


async def _targets(db: AsyncSession, account_uid: UUID) -> list[NativePushTarget]:
    result = await db.execute(
        select(NativePushDevice).where(
            NativePushDevice.account_uid == account_uid,
            NativePushDevice.revoked_at.is_(None),
        ).order_by(NativePushDevice.updated_at.desc())
    )
    return [NativePushTarget(UUID(str(item.uid)), item.token, item.provider, item.platform) for item in result.scalars().all()]


async def _receipt_status(db: AsyncSession, ledger_uid: UUID, device_uid: UUID) -> str | None:
    return (await db.execute(
        select(NativePushDeliveryReceipt.status).where(
            NativePushDeliveryReceipt.ledger_uid == ledger_uid,
            NativePushDeliveryReceipt.device_uid == device_uid,
        ).limit(1)
    )).scalar_one_or_none()


async def _mark_receipt(
    db: AsyncSession, claim: NativePushClaim, device_uid: UUID, *,
    status: str, provider_id: str | None = None, failure: str | None = None,
) -> bool:
    """Persist one device result before the Account ledger can be marked delivered.

    Stale workers cannot modify a receipt after their lease token was replaced.
    Success is never downgraded by a late retry.
    """
    if status not in {"delivered", "terminal"}:
        raise ValueError("Unsupported terminal native push receipt state")
    if await _claimed_row(db, claim) is None:
        return False
    record = (await db.execute(
        select(NativePushDeliveryReceipt).where(
            NativePushDeliveryReceipt.ledger_uid == claim.uid,
            NativePushDeliveryReceipt.device_uid == device_uid,
        ).with_for_update().limit(1)
    )).scalar_one_or_none()
    if record is None:
        record = NativePushDeliveryReceipt(
            ledger_uid=claim.uid, device_uid=device_uid, status=status,
            provider_message_id=provider_id[:180] if provider_id else None,
            failure_class=failure[:80] if failure else None,
        )
        db.add(record)
    elif record.status != "delivered":
        record.status = status
        record.provider_message_id = provider_id[:180] if provider_id else None
        record.failure_class = failure[:80] if failure else None
        record.updated_at = datetime.utcnow()
    await db.commit()
    return True


async def _revoke_terminal_device(session_factory: async_sessionmaker[AsyncSession], uid: UUID) -> None:
    async with session_factory() as db:
        result = await db.execute(select(NativePushDevice).where(NativePushDevice.uid == uid).limit(1))
        item = result.scalar_one_or_none()
        if item and item.revoked_at is None:
            item.revoked_at = datetime.utcnow()
            item.updated_at = datetime.utcnow()
            await db.commit()


async def run_native_push_worker(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    provider: FCMProvider | None = None,
    max_deliveries: int | None = None,
    now: datetime | None = None,
) -> NativePushStats:
    current = utc_naive(now or datetime.now(timezone.utc))
    provider = provider or FCMProvider()
    stats = NativePushStats()
    if not provider.configured:
        logger.error("Native push skipped: neither FCM nor APNs credentials are configured")
        return stats

    if not realtime_service.distributed:
        await realtime_service.start()
    if not realtime_service.distributed and not os.getenv("DEBUG", "false").lower() == "true":
        logger.error("Native push skipped: distributed Redis presence is unavailable")
        return stats
    stats.infrastructure_ready = True

    async with session_factory() as db:
        stats.accounts_scanned, stats.queued = await queue_native_push_for_unread(db, now=current)

    limit = max(1, min(int(max_deliveries or NATIVE_PUSH_BATCH_SIZE), 250))
    payload = build_messenger_native_push_payload()
    for _ in range(limit):
        async with session_factory() as db:
            claim = await _claim_one(db, current)
        if claim is None:
            break
        stats.claimed += 1

        # WebSocket presence survives while a native app sits in the background:
        # presence alone must never suppress the operating-system push.
        is_reply = claim.aggregate_key.startswith("space-reply:")
        async with session_factory() as db:
            preference = await db.get(MessageNotificationPreference, claim.account_uid)
            targets = await _targets(db, claim.account_uid)
            payload_for_claim = (
                await space_reply_claim_payload(db, claim.aggregate_key, claim.account_uid)
                if is_reply else
                (build_messenger_native_push_payload()
                 if await _eligible_unread_summary(db, claim.account_uid) is not None else None)
            )
        permitted = preference and (
            preference.native_push_space if is_reply else preference.native_push_messenger
        )
        if not permitted or not targets or payload_for_claim is None:
            async with session_factory() as db:
                await _finish(db, claim, state="suppressed", now=current, failure="native_push_opt_out_or_no_device")
            stats.suppressed += 1
            continue

        retryable_failure: NativePushProviderError | None = None
        permanent_failure: NativePushProviderError | None = None
        for target in targets:
            async with session_factory() as db:
                already = await _receipt_status(db, claim.uid, target.uid)
            if already in {"delivered", "terminal"}:
                continue
            try:
                provider_id = await provider.send(target, payload_for_claim)
                async with session_factory() as db:
                    await _mark_receipt(db, claim, target.uid, status="delivered", provider_id=provider_id)
            except NativePushProviderError as exc:
                if exc.terminal_device:
                    async with session_factory() as db:
                        await _mark_receipt(db, claim, target.uid, status="terminal", failure=exc.failure_class)
                    await _revoke_terminal_device(session_factory, target.uid)
                    stats.terminal_devices_revoked += 1
                elif exc.retryable:
                    retryable_failure = exc
                else:
                    async with session_factory() as db:
                        await _mark_receipt(db, claim, target.uid, status="terminal", failure=exc.failure_class)
                    permanent_failure = exc

        # A successful delivery to phone A NEVER counts as success for phone B
        # while B still needs a retry. Durable receipts skip A on the next run.
        if retryable_failure:
            async with session_factory() as db:
                retried = await _retry(db, claim, now=current, failure=retryable_failure.failure_class)
            if retried:
                stats.retried += 1
            else:
                stats.failed += 1
            continue

        async with session_factory() as db:
            completed = (await db.execute(
                select(NativePushDeliveryReceipt.status, NativePushDeliveryReceipt.provider_message_id).where(
                    NativePushDeliveryReceipt.ledger_uid == claim.uid,
                    NativePushDeliveryReceipt.status == "delivered",
                ).limit(1)
            )).first()
        if completed:
            async with session_factory() as db:
                await _finish(
                    db, claim, state="delivered", now=current,
                    provider_id=completed[1],
                    failure="native_push_partial_failure" if permanent_failure else None,
                )
            stats.delivered += 1
        else:
            failure = permanent_failure.failure_class if permanent_failure else "no_active_native_target"
            async with session_factory() as db:
                await _finish(db, claim, state="failed", now=current, failure=failure)
            stats.failed += 1

    return stats
