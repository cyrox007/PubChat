from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from components.device.crypto_model import DeviceCryptographicIdentity
from components.device.crypto_service import device_fingerprint


async def public_devices(db: AsyncSession, account_uid: UUID) -> list[dict]:
    result = await db.execute(
        select(DeviceCryptographicIdentity)
        .where(
            DeviceCryptographicIdentity.account_uid == account_uid,
            DeviceCryptographicIdentity.revoked_at.is_(None),
        )
        .order_by(DeviceCryptographicIdentity.created_at.asc())
    )
    devices = []
    for device in result.scalars().all():
        devices.append(
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
            }
        )
    return devices
