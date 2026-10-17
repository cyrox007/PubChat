from __future__ import annotations

import hashlib
import os
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import FileResponse

from components.message.e2ee_attachment_model import EncryptedPrivateAttachment
from components.message.model import PrivateMessage


MAX_E2EE_ATTACHMENT_CIPHERTEXT_BYTES = 25 * 1024 * 1024 + 16
E2EE_ATTACHMENT_STORAGE_ROOT = Path(
    os.getenv(
        "E2EE_ATTACHMENT_STORAGE_ROOT",
        str(Path(__file__).resolve().parents[3] / "private_uploads" / "e2ee"),
    )
).resolve()


def _storage_path(storage_name: str) -> Path:
    if not storage_name or Path(storage_name).name != storage_name:
        raise HTTPException(status_code=500, detail={"error_type": "invalid_encrypted_attachment_storage_name"})
    root = E2EE_ATTACHMENT_STORAGE_ROOT
    candidate = (root / storage_name).resolve()
    if candidate.parent != root:
        raise HTTPException(status_code=500, detail={"error_type": "invalid_encrypted_attachment_storage_path"})
    return candidate


async def store_encrypted_attachment(
    db: AsyncSession,
    *,
    account_uid: UUID,
    attachment_uid: UUID,
    upload: UploadFile,
) -> dict:
    existing = await db.get(EncryptedPrivateAttachment, attachment_uid)
    if existing:
        if existing.uploader_account_uid != account_uid:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error_type": "encrypted_attachment_conflict"})
        return {
            "attachment_uid": str(existing.uid),
            "ciphertext_size": existing.ciphertext_size,
            "ciphertext_sha256": existing.ciphertext_sha256,
            "attached": existing.message_uid is not None,
            "duplicate": True,
        }

    E2EE_ATTACHMENT_STORAGE_ROOT.mkdir(parents=True, exist_ok=True)
    storage_name = f"{uuid4().hex}.bin"
    destination = _storage_path(storage_name)
    digest = hashlib.sha256()
    total = 0

    try:
        with destination.open("xb") as output:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_E2EE_ATTACHMENT_CIPHERTEXT_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail={
                            "error_type": "encrypted_attachment_too_large",
                            "max_bytes": MAX_E2EE_ATTACHMENT_CIPHERTEXT_BYTES,
                        },
                    )
                digest.update(chunk)
                output.write(chunk)
        if total < 17:
            raise HTTPException(status_code=400, detail={"error_type": "encrypted_attachment_too_small"})

        attachment = EncryptedPrivateAttachment(
            uid=attachment_uid,
            uploader_account_uid=account_uid,
            storage_name=storage_name,
            ciphertext_size=total,
            ciphertext_sha256=digest.hexdigest(),
        )
        db.add(attachment)
        await db.commit()
        return {
            "attachment_uid": str(attachment.uid),
            "ciphertext_size": attachment.ciphertext_size,
            "ciphertext_sha256": attachment.ciphertext_sha256,
            "attached": False,
            "duplicate": False,
        }
    except Exception:
        await db.rollback()
        try:
            destination.unlink(missing_ok=True)
        except OSError:
            pass
        raise
    finally:
        await upload.close()


async def get_encrypted_attachment(
    db: AsyncSession,
    *,
    account_uid: UUID,
    attachment_uid: UUID,
) -> FileResponse:
    result = await db.execute(
        select(EncryptedPrivateAttachment, PrivateMessage)
        .outerjoin(PrivateMessage, PrivateMessage.uid == EncryptedPrivateAttachment.message_uid)
        .where(EncryptedPrivateAttachment.uid == attachment_uid)
        .limit(1)
    )
    row = result.first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error_type": "encrypted_attachment_not_found"})
    attachment, message = row
    allowed = attachment.uploader_account_uid == account_uid
    if message is not None:
        allowed = allowed or message.sender_uid == account_uid or message.receiver_uid == account_uid
    if not allowed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error_type": "encrypted_attachment_not_found"})

    path = _storage_path(attachment.storage_name)
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_410_GONE, detail={"error_type": "encrypted_attachment_missing"})
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=None,
        headers={
            "Cache-Control": "private, no-store, max-age=0",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'",
        },
    )


async def delete_pending_encrypted_attachment(
    db: AsyncSession,
    *,
    account_uid: UUID,
    attachment_uid: UUID,
) -> dict:
    attachment = await db.get(EncryptedPrivateAttachment, attachment_uid)
    if not attachment or attachment.uploader_account_uid != account_uid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error_type": "encrypted_attachment_not_found"})
    if attachment.message_uid is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error_type": "encrypted_attachment_already_attached"})

    path = _storage_path(attachment.storage_name)
    await db.delete(attachment)
    await db.commit()
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass
    return {"attachment_uid": str(attachment_uid), "deleted": True}


async def bind_encrypted_attachment(
    db: AsyncSession,
    *,
    account_uid: UUID,
    attachment_uid: UUID,
    message_uid: UUID,
) -> EncryptedPrivateAttachment:
    result = await db.execute(
        select(EncryptedPrivateAttachment)
        .where(EncryptedPrivateAttachment.uid == attachment_uid)
        .with_for_update()
        .limit(1)
    )
    attachment = result.scalar_one_or_none()
    if not attachment or attachment.uploader_account_uid != account_uid:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error_type": "encrypted_attachment_unavailable"})
    if attachment.message_uid is not None and attachment.message_uid != message_uid:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error_type": "encrypted_attachment_already_attached"})
    attachment.message_uid = message_uid
    from datetime import datetime

    attachment.attached_at = attachment.attached_at or datetime.utcnow()
    await db.flush()
    return attachment
