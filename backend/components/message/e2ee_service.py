from __future__ import annotations

import base64
from collections import defaultdict
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from components.device.crypto_model import DeviceCryptographicIdentity
from components.message.e2ee_model import PrivateMessageEnvelope


E2EE_VERSION = "pubchat-e2ee-v1"
MAX_ACCOUNT_CRYPTO_DEVICES = 20
MAX_ENVELOPE_CIPHERTEXT_BYTES = 16_384
MAX_INITIAL_HEADER_BYTES = 4_096
MAX_SESSION_COUNTER = 2_147_483_647


def _decode_b64url(value: str, *, max_bytes: int, field: str) -> bytes:
    if not isinstance(value, str) or not value or len(value) > max_bytes * 2:
        raise HTTPException(status_code=400, detail={"error_type": f"invalid_{field}"})
    normalized = value.rstrip("=")
    try:
        padding = "=" * ((4 - len(normalized) % 4) % 4)
        raw = base64.urlsafe_b64decode(normalized + padding)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"error_type": f"invalid_{field}"}) from exc
    if len(raw) > max_bytes:
        raise HTTPException(status_code=413, detail={"error_type": f"{field}_too_large"})
    if base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=") != normalized:
        raise HTTPException(status_code=400, detail={"error_type": f"invalid_{field}"})
    return raw


def _validate_initial_header(header: dict | None, sender_device: DeviceCryptographicIdentity) -> dict | None:
    if header is None:
        return None
    if not isinstance(header, dict):
        raise HTTPException(status_code=400, detail={"error_type": "invalid_e2ee_initial_header"})
    if len(str(header)) > MAX_INITIAL_HEADER_BYTES:
        raise HTTPException(status_code=413, detail={"error_type": "e2ee_initial_header_too_large"})
    required = {
        "ephemeral_key",
        "target_signed_prekey_id",
        "sender_identity_dh_key",
        "sender_identity_signing_key",
    }
    if not required.issubset(header):
        raise HTTPException(status_code=400, detail={"error_type": "invalid_e2ee_initial_header"})
    _decode_b64url(str(header["ephemeral_key"]), max_bytes=32, field="e2ee_ephemeral_key")
    if str(header["sender_identity_dh_key"]) != sender_device.identity_dh_key:
        raise HTTPException(status_code=409, detail={"error_type": "e2ee_sender_identity_mismatch"})
    if str(header["sender_identity_signing_key"]) != sender_device.identity_signing_key:
        raise HTTPException(status_code=409, detail={"error_type": "e2ee_sender_identity_mismatch"})
    try:
        signed_id = int(header["target_signed_prekey_id"])
        one_time_id = header.get("target_one_time_prekey_id")
        if signed_id < 0 or signed_id > MAX_SESSION_COUNTER:
            raise ValueError
        if one_time_id is not None and (int(one_time_id) < 0 or int(one_time_id) > MAX_SESSION_COUNTER):
            raise ValueError
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail={"error_type": "invalid_e2ee_prekey_id"}) from exc
    return header


async def active_devices_by_account(
    db: AsyncSession,
    account_uids: set[UUID],
) -> dict[UUID, dict[UUID, DeviceCryptographicIdentity]]:
    result = await db.execute(
        select(DeviceCryptographicIdentity).where(
            DeviceCryptographicIdentity.account_uid.in_(account_uids),
            DeviceCryptographicIdentity.revoked_at.is_(None),
        )
    )
    grouped: dict[UUID, dict[UUID, DeviceCryptographicIdentity]] = defaultdict(dict)
    for device in result.scalars().all():
        grouped[device.account_uid][device.uid] = device
    for account_uid, devices in grouped.items():
        if len(devices) > MAX_ACCOUNT_CRYPTO_DEVICES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error_type": "too_many_crypto_devices", "account_uid": str(account_uid)},
            )
    return grouped


async def validate_encrypted_envelopes(
    db: AsyncSession,
    *,
    sender_uid: UUID,
    receiver_uid: UUID,
    sender_device_uid: UUID,
    raw_envelopes: list[dict],
) -> list[dict]:
    if not isinstance(raw_envelopes, list) or not raw_envelopes:
        raise HTTPException(status_code=400, detail={"error_type": "e2ee_envelopes_required"})

    grouped = await active_devices_by_account(db, {sender_uid, receiver_uid})
    sender_devices = grouped.get(sender_uid, {})
    receiver_devices = grouped.get(receiver_uid, {})
    sender_device = sender_devices.get(sender_device_uid)
    if not sender_device:
        raise HTTPException(status_code=409, detail={"error_type": "e2ee_sender_device_unavailable"})
    if not receiver_devices:
        raise HTTPException(status_code=409, detail={"error_type": "e2ee_receiver_has_no_devices"})

    allowed_devices = {**sender_devices, **receiver_devices}
    expected_targets = set(sender_devices) | set(receiver_devices)
    seen_targets: set[UUID] = set()
    validated: list[dict] = []

    for envelope in raw_envelopes:
        if not isinstance(envelope, dict):
            raise HTTPException(status_code=400, detail={"error_type": "invalid_e2ee_envelope"})
        try:
            recipient_device_uid = UUID(str(envelope.get("recipient_device_uid")))
            session_id = UUID(str(envelope.get("session_id")))
            counter = int(envelope.get("counter"))
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail={"error_type": "invalid_e2ee_envelope"}) from exc
        if counter < 0 or counter > MAX_SESSION_COUNTER:
            raise HTTPException(status_code=400, detail={"error_type": "invalid_e2ee_counter"})
        if recipient_device_uid in seen_targets:
            raise HTTPException(status_code=400, detail={"error_type": "duplicate_e2ee_device_envelope"})
        target_device = allowed_devices.get(recipient_device_uid)
        if not target_device:
            raise HTTPException(status_code=400, detail={"error_type": "unknown_e2ee_recipient_device"})

        nonce_raw = _decode_b64url(str(envelope.get("nonce") or ""), max_bytes=12, field="e2ee_nonce")
        if len(nonce_raw) != 12:
            raise HTTPException(status_code=400, detail={"error_type": "invalid_e2ee_nonce"})
        ciphertext_raw = _decode_b64url(
            str(envelope.get("ciphertext") or ""),
            max_bytes=MAX_ENVELOPE_CIPHERTEXT_BYTES,
            field="e2ee_ciphertext",
        )
        if len(ciphertext_raw) < 16:
            raise HTTPException(status_code=400, detail={"error_type": "invalid_e2ee_ciphertext"})

        header = _validate_initial_header(envelope.get("initial_header"), sender_device)
        seen_targets.add(recipient_device_uid)
        validated.append(
            {
                "recipient_account_uid": target_device.account_uid,
                "recipient_device_uid": recipient_device_uid,
                "sender_device_uid": sender_device_uid,
                "session_id": session_id,
                "counter": counter,
                "nonce": envelope["nonce"],
                "ciphertext": envelope["ciphertext"],
                "initial_header": header,
            }
        )

    missing = expected_targets - seen_targets
    if missing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error_type": "e2ee_device_list_changed",
                "missing_device_uids": sorted(str(uid) for uid in missing),
            },
        )
    return validated


async def persist_envelopes(
    db: AsyncSession,
    *,
    message_uid: UUID,
    envelopes: list[dict],
) -> None:
    for envelope in envelopes:
        db.add(PrivateMessageEnvelope(message_uid=message_uid, **envelope))
    await db.flush()


async def envelopes_for_messages(
    db: AsyncSession,
    *,
    message_uids: list[UUID],
    account_uid: UUID,
) -> dict[str, list[dict]]:
    if not message_uids:
        return {}
    result = await db.execute(
        select(PrivateMessageEnvelope).where(
            PrivateMessageEnvelope.message_uid.in_(message_uids),
            PrivateMessageEnvelope.recipient_account_uid == account_uid,
        )
    )
    grouped: dict[str, list[dict]] = defaultdict(list)
    for envelope in result.scalars().all():
        grouped[str(envelope.message_uid)].append(
            {
                "recipient_device_uid": str(envelope.recipient_device_uid),
                "sender_device_uid": str(envelope.sender_device_uid),
                "session_id": str(envelope.session_id),
                "counter": envelope.counter,
                "nonce": envelope.nonce,
                "ciphertext": envelope.ciphertext,
                "initial_header": envelope.initial_header,
            }
        )
    return grouped
