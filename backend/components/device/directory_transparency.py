from __future__ import annotations

import hashlib
import json
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from components.device.crypto_model import DeviceCryptographicIdentity
from components.device.directory_transparency_model import DeviceDirectoryEvent
from components.device.fingerprint import device_fingerprint
from components.identity.model import Account


TRANSPARENCY_VERSION = "pubchat-device-directory-v1"
GENESIS_HASH = "0" * 64


def _canonical_json(value: dict | list) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _sha256_hex(domain: bytes, value: dict | list) -> str:
    return hashlib.sha256(domain + b"\x00" + _canonical_json(value)).hexdigest()


def canonical_directory_hash(devices: list[dict]) -> str:
    entries = sorted(
        [
            {
                "device_uid": str(item["device_uid"]),
                "key_version": int(item.get("key_version") or 1),
                "fingerprint": str(item["fingerprint"]),
                "identity_signing_key": str(item["identity_signing_key"]),
                "identity_dh_key": str(item["identity_dh_key"]),
            }
            for item in devices
        ],
        key=lambda item: item["device_uid"],
    )
    return _sha256_hex(b"pubchat-device-directory-snapshot-v1", entries)


async def _active_directory_projection(db: AsyncSession, account_uid: UUID) -> list[dict]:
    result = await db.execute(
        select(DeviceCryptographicIdentity)
        .where(
            DeviceCryptographicIdentity.account_uid == account_uid,
            DeviceCryptographicIdentity.revoked_at.is_(None),
        )
        .order_by(DeviceCryptographicIdentity.uid.asc())
    )
    return [
        {
            "device_uid": str(device.uid),
            "key_version": device.key_version,
            "identity_signing_key": device.identity_signing_key,
            "identity_dh_key": device.identity_dh_key,
            "fingerprint": device_fingerprint(device.identity_signing_key, device.identity_dh_key),
        }
        for device in result.scalars().all()
    ]


def _checkpoint_projection(event: DeviceDirectoryEvent | None) -> dict | None:
    if event is None:
        return None
    return {
        "version": TRANSPARENCY_VERSION,
        "sequence": int(event.sequence),
        "event_hash": event.event_hash,
        "previous_hash": event.previous_hash,
        "directory_hash": event.directory_hash,
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


async def latest_directory_checkpoint(db: AsyncSession, account_uid: UUID) -> dict | None:
    result = await db.execute(
        select(DeviceDirectoryEvent)
        .where(DeviceDirectoryEvent.account_uid == account_uid)
        .order_by(DeviceDirectoryEvent.sequence.desc())
        .limit(1)
    )
    return _checkpoint_projection(result.scalar_one_or_none())


async def append_directory_event(
    db: AsyncSession,
    *,
    account_uid: UUID,
    event_type: str,
    device: DeviceCryptographicIdentity | None,
) -> DeviceDirectoryEvent:
    """Append one Account-scoped directory event inside the caller transaction.

    Locking the Account row serializes sequence assignment for concurrent device
    registration/revocation requests without introducing a separate counter row.
    """

    await db.execute(select(Account.uid).where(Account.uid == account_uid).with_for_update())
    latest_result = await db.execute(
        select(DeviceDirectoryEvent)
        .where(DeviceDirectoryEvent.account_uid == account_uid)
        .order_by(DeviceDirectoryEvent.sequence.desc())
        .limit(1)
    )
    latest = latest_result.scalar_one_or_none()
    sequence = int(latest.sequence) + 1 if latest else 1
    previous_hash = latest.event_hash if latest else GENESIS_HASH
    directory_hash = canonical_directory_hash(await _active_directory_projection(db, account_uid))

    device_payload = None
    if device is not None:
        device_payload = {
            "device_uid": str(device.uid),
            "key_version": int(device.key_version),
            "fingerprint": device_fingerprint(device.identity_signing_key, device.identity_dh_key),
            "identity_signing_key": device.identity_signing_key,
            "identity_dh_key": device.identity_dh_key,
        }
    payload = {
        "version": TRANSPARENCY_VERSION,
        "account_uid": str(account_uid),
        "sequence": sequence,
        "event_type": event_type,
        "device": device_payload,
        "previous_hash": previous_hash,
        "directory_hash": directory_hash,
    }
    event_hash = _sha256_hex(b"pubchat-device-directory-event-v1", payload)
    event = DeviceDirectoryEvent(
        account_uid=account_uid,
        sequence=sequence,
        event_type=event_type,
        device_uid=device.uid if device is not None else None,
        key_version=device.key_version if device is not None else None,
        fingerprint=device_payload["fingerprint"] if device_payload else None,
        identity_signing_key=device.identity_signing_key if device is not None else None,
        identity_dh_key=device.identity_dh_key if device is not None else None,
        previous_hash=previous_hash,
        directory_hash=directory_hash,
        event_hash=event_hash,
        created_at=datetime.utcnow(),
    )
    db.add(event)
    await db.flush()
    return event


async def directory_history(
    db: AsyncSession,
    *,
    account_uid: UUID,
    after_sequence: int = 0,
    limit: int = 100,
) -> list[dict]:
    safe_limit = max(1, min(200, int(limit)))
    result = await db.execute(
        select(DeviceDirectoryEvent)
        .where(
            DeviceDirectoryEvent.account_uid == account_uid,
            DeviceDirectoryEvent.sequence > max(0, int(after_sequence)),
        )
        .order_by(DeviceDirectoryEvent.sequence.asc())
        .limit(safe_limit)
    )
    return [
        {
            "version": TRANSPARENCY_VERSION,
            "sequence": int(event.sequence),
            "event_type": event.event_type,
            "device_uid": str(event.device_uid) if event.device_uid else None,
            "key_version": event.key_version,
            "fingerprint": event.fingerprint,
            "previous_hash": event.previous_hash,
            "directory_hash": event.directory_hash,
            "event_hash": event.event_hash,
            "created_at": event.created_at.isoformat() if event.created_at else None,
        }
        for event in result.scalars().all()
    ]
