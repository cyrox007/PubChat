from __future__ import annotations

import base64
import hashlib
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from components.device.crypto_model import DeviceCryptographicIdentity, DeviceOneTimePreKey
from components.device.crypto_schemas import (
    DeviceRegistrationRequest,
    OneTimePreKeyInput,
    SignedPreKeyInput,
)
from components.identity.model import Account


MAX_AVAILABLE_ONE_TIME_PREKEYS = 200


def _key_bytes(value: str) -> bytes:
    padding = "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode(value + padding)


def device_fingerprint(identity_signing_key: str, identity_dh_key: str) -> str:
    digest = hashlib.sha256(
        b"pubchat-device-identity-v1\x00"
        + _key_bytes(identity_signing_key)
        + _key_bytes(identity_dh_key)
    ).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _device_projection(device: DeviceCryptographicIdentity, *, prekey_count: int | None = None) -> dict:
    return {
        "device_uid": str(device.uid),
        "account_uid": str(device.account_uid),
        "device_label": device.device_label,
        "key_version": device.key_version,
        "identity_signing_key": device.identity_signing_key,
        "identity_dh_key": device.identity_dh_key,
        "fingerprint": device_fingerprint(device.identity_signing_key, device.identity_dh_key),
        "signed_prekey": {
            "id": device.signed_prekey_id,
            "public_key": device.signed_prekey_key,
            "signature": device.signed_prekey_signature,
            "created_at": device.signed_prekey_created_at.isoformat() if device.signed_prekey_created_at else None,
        },
        "available_one_time_prekeys": prekey_count,
        "created_at": device.created_at.isoformat() if device.created_at else None,
        "last_seen_at": device.last_seen_at.isoformat() if device.last_seen_at else None,
        "revoked_at": device.revoked_at.isoformat() if device.revoked_at else None,
    }


async def _device_for_owner(
    db: AsyncSession,
    *,
    account_uid: UUID,
    device_uid: UUID,
    require_active: bool = True,
) -> DeviceCryptographicIdentity:
    result = await db.execute(
        select(DeviceCryptographicIdentity).where(
            DeviceCryptographicIdentity.uid == device_uid,
            DeviceCryptographicIdentity.account_uid == account_uid,
        ).limit(1)
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error_type": "crypto_device_not_found"})
    if require_active and device.revoked_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error_type": "crypto_device_revoked"})
    return device


async def _available_prekey_count(db: AsyncSession, device_uid: UUID) -> int:
    result = await db.execute(
        select(func.count(DeviceOneTimePreKey.id)).where(
            DeviceOneTimePreKey.device_uid == device_uid,
            DeviceOneTimePreKey.claimed_at.is_(None),
        )
    )
    return int(result.scalar_one() or 0)


async def _add_one_time_prekeys(
    db: AsyncSession,
    *,
    device: DeviceCryptographicIdentity,
    prekeys: list[OneTimePreKeyInput],
) -> int:
    if not prekeys:
        return await _available_prekey_count(db, device.uid)

    requested = {item.id: item for item in prekeys}
    existing_result = await db.execute(
        select(DeviceOneTimePreKey).where(
            DeviceOneTimePreKey.device_uid == device.uid,
            DeviceOneTimePreKey.prekey_id.in_(requested.keys()),
        )
    )
    existing = {int(item.prekey_id): item for item in existing_result.scalars().all()}
    conflicting = sorted(
        prekey_id
        for prekey_id, record in existing.items()
        if record.public_key != requested[prekey_id].public_key
    )
    if conflicting:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_type": "one_time_prekey_id_conflict", "ids": conflicting},
        )

    new_prekeys = [item for item in prekeys if item.id not in existing]
    current_count = await _available_prekey_count(db, device.uid)
    if current_count + len(new_prekeys) > MAX_AVAILABLE_ONE_TIME_PREKEYS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_type": "too_many_one_time_prekeys", "max_available": MAX_AVAILABLE_ONE_TIME_PREKEYS},
        )

    for item in new_prekeys:
        db.add(
            DeviceOneTimePreKey(
                device_uid=device.uid,
                prekey_id=item.id,
                public_key=item.public_key,
            )
        )
    if new_prekeys:
        await db.flush()
    return current_count + len(new_prekeys)


async def register_device(
    db: AsyncSession,
    *,
    account_uid: UUID,
    payload: DeviceRegistrationRequest,
) -> dict:
    account = await db.get(Account, account_uid)
    if not account or account.deleted_at is not None or account.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error_type": "account_unavailable"})

    existing = await db.get(DeviceCryptographicIdentity, payload.device_uid)
    now = datetime.utcnow()
    if existing:
        if existing.account_uid != account_uid:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error_type": "crypto_device_identity_conflict"})
        if existing.revoked_at is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error_type": "crypto_device_revoked"})
        if (
            existing.identity_signing_key != payload.identity_signing_key
            or existing.identity_dh_key != payload.identity_dh_key
            or existing.key_version != payload.key_version
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error_type": "crypto_device_identity_immutable"},
            )
        if existing.signed_prekey_id == payload.signed_prekey.id and (
            existing.signed_prekey_key != payload.signed_prekey.public_key
            or existing.signed_prekey_signature != payload.signed_prekey.signature
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error_type": "signed_prekey_id_reuse"},
            )
        existing.device_label = payload.device_label
        if existing.signed_prekey_id != payload.signed_prekey.id:
            existing.signed_prekey_id = payload.signed_prekey.id
            existing.signed_prekey_key = payload.signed_prekey.public_key
            existing.signed_prekey_signature = payload.signed_prekey.signature
            existing.signed_prekey_created_at = now
        existing.updated_at = now
        existing.last_seen_at = now
        device = existing
    else:
        device = DeviceCryptographicIdentity(
            uid=payload.device_uid,
            account_uid=account_uid,
            device_label=payload.device_label,
            key_version=payload.key_version,
            identity_signing_key=payload.identity_signing_key,
            identity_dh_key=payload.identity_dh_key,
            signed_prekey_id=payload.signed_prekey.id,
            signed_prekey_key=payload.signed_prekey.public_key,
            signed_prekey_signature=payload.signed_prekey.signature,
            signed_prekey_created_at=now,
            last_seen_at=now,
        )
        db.add(device)
        await db.flush()

    count = await _add_one_time_prekeys(db, device=device, prekeys=payload.one_time_prekeys)
    await db.commit()
    await db.refresh(device)
    return _device_projection(device, prekey_count=count)


async def list_own_devices(db: AsyncSession, *, account_uid: UUID) -> list[dict]:
    result = await db.execute(
        select(DeviceCryptographicIdentity)
        .where(DeviceCryptographicIdentity.account_uid == account_uid)
        .order_by(DeviceCryptographicIdentity.created_at.asc())
    )
    devices = list(result.scalars().all())
    projections: list[dict] = []
    for device in devices:
        projections.append(
            _device_projection(
                device,
                prekey_count=await _available_prekey_count(db, device.uid),
            )
        )
    return projections


async def rotate_signed_prekey(
    db: AsyncSession,
    *,
    account_uid: UUID,
    device_uid: UUID,
    signed_prekey: SignedPreKeyInput,
) -> dict:
    device = await _device_for_owner(db, account_uid=account_uid, device_uid=device_uid)
    if signed_prekey.id == device.signed_prekey_id and (
        signed_prekey.public_key != device.signed_prekey_key
        or signed_prekey.signature != device.signed_prekey_signature
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"error_type": "signed_prekey_id_reuse"},
        )
    if signed_prekey.id != device.signed_prekey_id:
        device.signed_prekey_id = signed_prekey.id
        device.signed_prekey_key = signed_prekey.public_key
        device.signed_prekey_signature = signed_prekey.signature
        device.signed_prekey_created_at = datetime.utcnow()
    device.updated_at = datetime.utcnow()
    device.last_seen_at = datetime.utcnow()
    await db.commit()
    await db.refresh(device)
    return _device_projection(device, prekey_count=await _available_prekey_count(db, device.uid))


async def add_one_time_prekeys(
    db: AsyncSession,
    *,
    account_uid: UUID,
    device_uid: UUID,
    prekeys: list[OneTimePreKeyInput],
) -> dict:
    device = await _device_for_owner(db, account_uid=account_uid, device_uid=device_uid)
    count = await _add_one_time_prekeys(db, device=device, prekeys=prekeys)
    device.last_seen_at = datetime.utcnow()
    await db.commit()
    return {"device_uid": str(device.uid), "available_one_time_prekeys": count}


async def revoke_device(
    db: AsyncSession,
    *,
    account_uid: UUID,
    device_uid: UUID,
) -> dict:
    device = await _device_for_owner(db, account_uid=account_uid, device_uid=device_uid, require_active=False)
    if device.revoked_at is None:
        device.revoked_at = datetime.utcnow()
        device.updated_at = datetime.utcnow()
        await db.execute(delete(DeviceOneTimePreKey).where(DeviceOneTimePreKey.device_uid == device.uid))
        await db.commit()
    return {"device_uid": str(device.uid), "revoked": True, "revoked_at": device.revoked_at.isoformat() if device.revoked_at else None}


async def claim_prekey_bundle(
    db: AsyncSession,
    *,
    target_account_uid: UUID,
) -> dict:
    account = await db.get(Account, target_account_uid)
    if not account or account.deleted_at is not None or account.status != "active":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error_type": "account_not_found"})

    result = await db.execute(
        select(DeviceCryptographicIdentity)
        .where(
            DeviceCryptographicIdentity.account_uid == target_account_uid,
            DeviceCryptographicIdentity.revoked_at.is_(None),
        )
        .order_by(DeviceCryptographicIdentity.created_at.asc())
    )
    devices = list(result.scalars().all())
    bundles: list[dict] = []
    now = datetime.utcnow()

    for device in devices:
        prekey_result = await db.execute(
            select(DeviceOneTimePreKey)
            .where(
                DeviceOneTimePreKey.device_uid == device.uid,
                DeviceOneTimePreKey.claimed_at.is_(None),
            )
            .order_by(DeviceOneTimePreKey.id.asc())
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        one_time = prekey_result.scalar_one_or_none()
        if one_time:
            one_time.claimed_at = now

        bundles.append(
            {
                "device_uid": str(device.uid),
                "key_version": device.key_version,
                "identity_signing_key": device.identity_signing_key,
                "identity_dh_key": device.identity_dh_key,
                "fingerprint": device_fingerprint(device.identity_signing_key, device.identity_dh_key),
                "signed_prekey": {
                    "id": device.signed_prekey_id,
                    "public_key": device.signed_prekey_key,
                    "signature": device.signed_prekey_signature,
                },
                "one_time_prekey": (
                    {"id": one_time.prekey_id, "public_key": one_time.public_key}
                    if one_time
                    else None
                ),
            }
        )

    await db.commit()
    return {
        "account_uid": str(target_account_uid),
        "devices": bundles,
        "bundle_version": "v1",
    }
