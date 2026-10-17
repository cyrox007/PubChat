from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from components.device.crypto_model import DeviceCryptographicIdentity
from components.message.encryption_policy_model import PrivateConversationEncryption
from settings import config


SYSTEM_POLICIES = frozenset({"disabled", "optional", "required"})
CONVERSATION_MODES = frozenset({"plaintext", "e2ee"})


def system_policy() -> str:
    value = str(config.MESSENGER_E2EE_POLICY or "optional").strip().lower()
    if value not in SYSTEM_POLICIES:
        raise RuntimeError("MESSENGER_E2EE_POLICY must be disabled, optional or required")
    return value


def _pair(left: UUID, right: UUID) -> tuple[UUID, UUID]:
    if left == right:
        return left, right
    return (left, right) if left.int < right.int else (right, left)


async def active_crypto_device_count(db: AsyncSession, account_uid: UUID) -> int:
    result = await db.execute(
        select(func.count(DeviceCryptographicIdentity.uid)).where(
            DeviceCryptographicIdentity.account_uid == account_uid,
            DeviceCryptographicIdentity.revoked_at.is_(None),
        )
    )
    return int(result.scalar_one() or 0)


async def configured_mode(db: AsyncSession, account_uid: UUID, peer_uid: UUID) -> str | None:
    low, high = _pair(account_uid, peer_uid)
    if low == high:
        return None
    row = await db.get(PrivateConversationEncryption, {"account_low_uid": low, "account_high_uid": high})
    return row.mode if row else None


async def conversation_policy(db: AsyncSession, account_uid: UUID, peer_uid: UUID) -> dict:
    policy = system_policy()
    stored = await configured_mode(db, account_uid, peer_uid)
    own_devices = await active_crypto_device_count(db, account_uid)
    peer_devices = await active_crypto_device_count(db, peer_uid)
    crypto_ready = own_devices > 0 and peer_devices > 0

    if policy == "disabled":
        effective = "plaintext"
    elif policy == "required":
        effective = "e2ee"
    elif stored in CONVERSATION_MODES:
        effective = stored
    else:
        # Preserve the pre-policy rollout semantics for conversations that have
        # never made an explicit choice: crypto-capable peers remain encrypted,
        # while peers without devices remain reachable in plaintext.
        effective = "e2ee" if peer_devices > 0 else "plaintext"

    return {
        "system_policy": policy,
        "configured_mode": stored,
        "effective_mode": effective,
        "can_change": policy == "optional" and account_uid != peer_uid,
        "crypto_ready": crypto_ready,
        "own_crypto_devices": own_devices,
        "peer_crypto_devices": peer_devices,
    }


async def set_conversation_mode(
    db: AsyncSession,
    *,
    account_uid: UUID,
    peer_uid: UUID,
    mode: str,
) -> dict:
    if system_policy() != "optional":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_type": "conversation_encryption_managed_by_system"},
        )
    normalized = str(mode or "").strip().lower()
    if normalized not in CONVERSATION_MODES:
        raise HTTPException(status_code=422, detail={"error_type": "invalid_encryption_mode"})
    if account_uid == peer_uid:
        raise HTTPException(status_code=409, detail={"error_type": "conversation_encryption_self_not_supported"})

    low, high = _pair(account_uid, peer_uid)
    row = await db.get(PrivateConversationEncryption, {"account_low_uid": low, "account_high_uid": high})
    now = datetime.utcnow()
    if row is None:
        row = PrivateConversationEncryption(
            account_low_uid=low,
            account_high_uid=high,
            mode=normalized,
            set_by_account_uid=account_uid,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        row.mode = normalized
        row.set_by_account_uid = account_uid
        row.updated_at = now
    await db.commit()
    return await conversation_policy(db, account_uid, peer_uid)


async def assert_plaintext_allowed(db: AsyncSession, sender_uid: UUID, receiver_uid: UUID) -> dict:
    policy = await conversation_policy(db, sender_uid, receiver_uid)
    if policy["effective_mode"] != "plaintext":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_type": "conversation_requires_e2ee", "encryption": policy},
        )
    return policy


async def assert_e2ee_allowed(db: AsyncSession, sender_uid: UUID, receiver_uid: UUID) -> dict:
    policy = await conversation_policy(db, sender_uid, receiver_uid)
    if policy["effective_mode"] != "e2ee":
        error_type = "e2ee_disabled_by_system" if policy["system_policy"] == "disabled" else "conversation_plaintext_mode"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_type": error_type, "encryption": policy},
        )
    if not policy["crypto_ready"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_type": "e2ee_devices_not_ready", "encryption": policy},
        )
    return policy
