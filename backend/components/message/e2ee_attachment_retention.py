from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from components.message.e2ee_attachment import E2EE_ATTACHMENT_STORAGE_ROOT
from components.message.e2ee_attachment_model import EncryptedPrivateAttachment


DEFAULT_PENDING_RETENTION_HOURS = 24
DEFAULT_ORPHAN_GRACE_HOURS = 24
DEFAULT_BATCH_SIZE = 100
MAX_BATCH_SIZE = 1000
_STORAGE_NAME_RE = re.compile(r"^[0-9a-f]{32}\.bin$")


def _bounded_positive_env(name: str, default: int, maximum: int) -> int:
    value = int(os.getenv(name, str(default)).strip())
    return max(1, min(maximum, value))


def pending_retention_hours() -> int:
    return _bounded_positive_env("E2EE_ATTACHMENT_PENDING_RETENTION_HOURS", DEFAULT_PENDING_RETENTION_HOURS, 24 * 30)


def orphan_grace_hours() -> int:
    return _bounded_positive_env("E2EE_ATTACHMENT_ORPHAN_GRACE_HOURS", DEFAULT_ORPHAN_GRACE_HOURS, 24 * 30)


def retention_batch_size() -> int:
    return _bounded_positive_env("E2EE_ATTACHMENT_RETENTION_BATCH_SIZE", DEFAULT_BATCH_SIZE, MAX_BATCH_SIZE)


@dataclass(slots=True)
class E2EEAttachmentRetentionStats:
    pending_candidates: int = 0
    pending_rows_deleted: int = 0
    pending_files_deleted: int = 0
    pending_files_missing: int = 0
    orphan_candidates: int = 0
    orphan_files_deleted: int = 0
    skipped_symlinks: int = 0
    failed: int = 0


def _safe_storage_file(root: Path, storage_name: str) -> Path | None:
    if not _STORAGE_NAME_RE.fullmatch(storage_name or ""):
        return None
    candidate = root / storage_name
    if candidate.is_symlink():
        return None
    try:
        resolved = candidate.resolve(strict=False)
    except OSError:
        return None
    if resolved.parent != root.resolve():
        return None
    return candidate


def _old_orphan_candidates(root: Path, *, cutoff: datetime, limit: int) -> tuple[list[Path], int]:
    if not root.exists():
        return [], 0
    candidates: list[Path] = []
    skipped_symlinks = 0
    cutoff_ts = cutoff.timestamp()
    try:
        entries = root.iterdir()
    except OSError:
        return [], 0
    for path in entries:
        if len(candidates) >= limit:
            break
        try:
            if path.is_symlink():
                skipped_symlinks += 1
                continue
            if not _STORAGE_NAME_RE.fullmatch(path.name):
                continue
            if not path.is_file():
                continue
            if path.stat().st_mtime > cutoff_ts:
                continue
        except OSError:
            continue
        candidates.append(path)
    return candidates, skipped_symlinks


async def cleanup_e2ee_attachment_storage(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    root: Path | None = None,
    batch_size: int | None = None,
    pending_hours: int | None = None,
    orphan_hours: int | None = None,
    dry_run: bool = False,
) -> E2EEAttachmentRetentionStats:
    """Remove expired pending ciphertext and unreferenced private-storage files.

    Bound attachments are never selected. Metadata is committed before file
    deletion; a failed unlink is therefore recoverable by a later orphan sweep.
    """

    current = now or datetime.utcnow()
    storage_root = (root or E2EE_ATTACHMENT_STORAGE_ROOT).resolve()
    size = max(1, min(MAX_BATCH_SIZE, batch_size or retention_batch_size()))
    pending_cutoff = current - timedelta(hours=pending_hours or pending_retention_hours())
    orphan_cutoff = current - timedelta(hours=orphan_hours or orphan_grace_hours())
    stats = E2EEAttachmentRetentionStats()

    result = await db.execute(
        select(EncryptedPrivateAttachment)
        .where(
            EncryptedPrivateAttachment.message_uid.is_(None),
            EncryptedPrivateAttachment.created_at <= pending_cutoff,
        )
        .order_by(EncryptedPrivateAttachment.created_at.asc())
        .limit(size)
        .with_for_update(skip_locked=True)
    )
    pending = list(result.scalars().all())
    stats.pending_candidates = len(pending)
    pending_files = [
        _safe_storage_file(storage_root, attachment.storage_name)
        for attachment in pending
    ]

    if not dry_run and pending:
        for attachment in pending:
            await db.delete(attachment)
        await db.commit()
        stats.pending_rows_deleted = len(pending)
        for path in pending_files:
            if path is None:
                stats.failed += 1
                continue
            try:
                existed = path.exists()
                path.unlink(missing_ok=True)
                if existed:
                    stats.pending_files_deleted += 1
                else:
                    stats.pending_files_missing += 1
            except OSError:
                stats.failed += 1
    else:
        await db.rollback()

    scan_limit = max(size, min(MAX_BATCH_SIZE * 4, size * 4))
    filesystem_candidates, skipped = _old_orphan_candidates(
        storage_root,
        cutoff=orphan_cutoff,
        limit=scan_limit,
    )
    stats.skipped_symlinks = skipped
    if not filesystem_candidates:
        return stats

    names = [path.name for path in filesystem_candidates]
    referenced_result = await db.execute(
        select(EncryptedPrivateAttachment.storage_name).where(
            EncryptedPrivateAttachment.storage_name.in_(names)
        )
    )
    referenced = set(referenced_result.scalars().all())
    orphan_files = [path for path in filesystem_candidates if path.name not in referenced][:size]
    stats.orphan_candidates = len(orphan_files)

    if dry_run:
        return stats

    for path in orphan_files:
        try:
            if path.is_symlink() or not path.is_file():
                stats.skipped_symlinks += int(path.is_symlink())
                continue
            path.unlink(missing_ok=True)
            stats.orphan_files_deleted += 1
        except OSError:
            stats.failed += 1

    return stats
