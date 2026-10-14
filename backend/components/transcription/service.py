from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from components.message.model import Message, PrivateMessage
from components.transcription.model import MediaTranscriptionJob
from components.transcription.provider import TranscriptionProviderError, build_transcription_provider
from components.transcription.settings import transcription_config


TRANSCRIBABLE_TYPES = {"voice", "audio", "video"}


def _media_url(metadata: dict | None, content_type: str) -> str | None:
    metadata = metadata if isinstance(metadata, dict) else {}
    if content_type == "voice" and metadata.get("voice"):
        return str(metadata["voice"])
    files = metadata.get("files") if isinstance(metadata.get("files"), list) else []
    if files:
        first = files[0]
        if isinstance(first, dict) and first.get("url"):
            return str(first["url"])
        if isinstance(first, str):
            return first
    return None


def _with_transcription(metadata: dict | None, *, status: str, text: str = "", language: str | None = None, segments: list | None = None) -> dict:
    value = dict(metadata or {})
    value["transcription"] = {
        "status": status,
        "text": text,
        "language": language,
        "segments": segments or [],
    }
    return value


async def _load_message(db: AsyncSession, surface: str, message_uid: UUID):
    model = Message if surface == "room" else PrivateMessage if surface == "messenger" else None
    return await db.get(model, message_uid) if model else None


async def _set_message_metadata(db: AsyncSession, surface: str, message_uid: UUID, metadata: dict) -> bool:
    message = await _load_message(db, surface, message_uid)
    if not message:
        return False
    message.media_metadata = metadata
    return True


async def enqueue_message_transcription(
    db: AsyncSession,
    *,
    surface: str,
    message_uid: UUID | str,
    content_type: str,
    media_metadata: dict | None,
    commit: bool = True,
) -> MediaTranscriptionJob | None:
    if content_type not in TRANSCRIBABLE_TYPES:
        return None
    url = _media_url(media_metadata, content_type)
    if not url:
        return None
    uid = UUID(str(message_uid))
    existing = (
        await db.execute(
            select(MediaTranscriptionJob).where(
                MediaTranscriptionJob.surface == surface,
                MediaTranscriptionJob.message_uid == uid,
            )
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    job = MediaTranscriptionJob(surface=surface, message_uid=uid, media_url=url, status="pending")
    db.add(job)
    await _set_message_metadata(db, surface, uid, _with_transcription(media_metadata, status="pending"))
    if commit:
        await db.commit()
    return job


async def discover_transcription_jobs(db: AsyncSession, *, scan_limit: int = 200) -> int:
    """Find newly persisted voice/audio/video messages without coupling to one transport.

    Both websocket surfaces are covered, including old messages created while the
    worker/provider was temporarily unavailable.
    """
    discovered = 0
    specs = (("room", Message), ("messenger", PrivateMessage))
    for surface, model in specs:
        messages = (
            await db.execute(
                select(model)
                .where(model.content_type.in_(TRANSCRIBABLE_TYPES))
                .order_by(model.created_at.desc())
                .limit(scan_limit)
            )
        ).scalars().all()
        if not messages:
            continue
        existing = set(
            (
                await db.execute(
                    select(MediaTranscriptionJob.message_uid).where(
                        MediaTranscriptionJob.surface == surface,
                        MediaTranscriptionJob.message_uid.in_([message.uid for message in messages]),
                    )
                )
            ).scalars().all()
        )
        for message in messages:
            if message.uid in existing:
                continue
            url = _media_url(message.media_metadata, message.content_type)
            if not url:
                continue
            db.add(
                MediaTranscriptionJob(
                    surface=surface,
                    message_uid=message.uid,
                    media_url=url,
                    status="pending",
                )
            )
            message.media_metadata = _with_transcription(message.media_metadata, status="pending")
            discovered += 1
    if discovered:
        await db.commit()
    return discovered


@dataclass(slots=True)
class TranscriptionWorkerStats:
    discovered: int = 0
    claimed: int = 0
    completed: int = 0
    retried: int = 0
    failed: int = 0
    infrastructure_ready: bool = True


async def _process_job(db: AsyncSession, job: MediaTranscriptionJob) -> str:
    try:
        provider = build_transcription_provider()
    except TranscriptionProviderError:
        job.status = "pending"
        job.error_code = "provider_not_configured"
        job.available_at = datetime.utcnow() + timedelta(minutes=5)
        await db.commit()
        return "retry"

    job.status = "processing"
    job.started_at = datetime.utcnow()
    job.attempts = int(job.attempts or 0) + 1
    job.provider_key = provider.key
    job.model_name = provider.model_name
    message = await _load_message(db, job.surface, job.message_uid)
    if not message:
        job.status = "failed"
        job.error_code = "message_missing"
        job.completed_at = datetime.utcnow()
        await db.commit()
        return "failed"
    message.media_metadata = _with_transcription(message.media_metadata, status="processing")
    await db.commit()

    try:
        result = await provider.transcribe(media_url=job.media_url, surface=job.surface, message_uid=str(job.message_uid))
    except TranscriptionProviderError as exc:
        message = await _load_message(db, job.surface, job.message_uid)
        if job.attempts >= transcription_config.max_attempts:
            job.status = "failed"
            job.error_code = str(exc)[:64]
            job.completed_at = datetime.utcnow()
            if message:
                message.media_metadata = _with_transcription(message.media_metadata, status="failed")
            await db.commit()
            return "failed"
        job.status = "pending"
        job.error_code = str(exc)[:64]
        job.available_at = datetime.utcnow() + timedelta(seconds=min(1800, 15 * (2 ** max(0, job.attempts - 1))))
        if message:
            message.media_metadata = _with_transcription(message.media_metadata, status="pending")
        await db.commit()
        return "retry"

    job.status = "ready"
    job.language = result.language
    job.text = result.text
    job.segments = [segment.model_dump() for segment in result.segments]
    job.completed_at = datetime.utcnow()
    job.error_code = None
    message = await _load_message(db, job.surface, job.message_uid)
    if message:
        message.media_metadata = _with_transcription(
            message.media_metadata,
            status="ready",
            text=result.text,
            language=result.language,
            segments=job.segments,
        )
    await db.commit()
    return "completed"


async def run_transcription_worker(session_factory: async_sessionmaker, *, batch_size: int | None = None) -> TranscriptionWorkerStats:
    stats = TranscriptionWorkerStats()
    limit = batch_size or transcription_config.batch_size
    async with session_factory() as db:
        stats.discovered = await discover_transcription_jobs(db, scan_limit=max(200, limit * 5))
        now = datetime.utcnow()
        jobs = (
            await db.execute(
                select(MediaTranscriptionJob)
                .where(MediaTranscriptionJob.status == "pending", MediaTranscriptionJob.available_at <= now)
                .order_by(MediaTranscriptionJob.created_at.asc())
                .with_for_update(skip_locked=True)
                .limit(limit)
            )
        ).scalars().all()
        stats.claimed = len(jobs)
        for job in jobs:
            outcome = await _process_job(db, job)
            if outcome == "completed": stats.completed += 1
            elif outcome == "retry": stats.retried += 1
            else: stats.failed += 1
    return stats
