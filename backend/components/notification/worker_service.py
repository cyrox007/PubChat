from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from components.identity.model import Account
from components.notification.model import ActivityReminderPreference, MessageNotificationPreference, NotificationWorkerState
from components.notification.birthday import sync_friend_birthdays
from components.notification.service import sync_activity_reminders
from utils.logger import setup_logger


logger = setup_logger(__name__)

WORKER_NAME_ACTIVITY_REMINDERS = "activity-reminders"
DEFAULT_WORKER_BATCH_SIZE = 100
MAX_WORKER_BATCH_SIZE = 250
DEFAULT_MAX_BATCHES = 20
MAX_WORKER_BATCHES = 100


@dataclass
class ReminderWorkerStats:
    acquired: bool = False
    wrapped: bool = False
    batches: int = 0
    accounts_seen: int = 0
    accounts_synced: int = 0
    accounts_failed: int = 0


async def reminder_account_page(
    db: AsyncSession,
    *,
    after_uid: UUID | None = None,
    limit: int = DEFAULT_WORKER_BATCH_SIZE,
) -> list[UUID]:
    bounded_limit = max(1, min(int(limit), MAX_WORKER_BATCH_SIZE))
    stmt = (
        select(Account.uid)
        .outerjoin(ActivityReminderPreference, Account.uid == ActivityReminderPreference.account_uid)
        .outerjoin(MessageNotificationPreference, Account.uid == MessageNotificationPreference.account_uid)
        .where(
            or_(
                ActivityReminderPreference.enabled.is_(True),
                MessageNotificationPreference.friend_birthday_reminders.is_(True),
            ),
            Account.status == "active",
            Account.deleted_at.is_(None),
        )
        .distinct()
        .order_by(Account.uid.asc())
        .limit(bounded_limit)
    )
    if after_uid is not None:
        stmt = stmt.where(Account.uid > after_uid)

    result = await db.execute(stmt)
    return [account_uid for (account_uid,) in result.all()]


async def lock_worker_state(
    db: AsyncSession,
    worker_name: str = WORKER_NAME_ACTIVITY_REMINDERS,
) -> NotificationWorkerState | None:
    result = await db.execute(
        select(NotificationWorkerState)
        .where(NotificationWorkerState.worker_name == worker_name)
        .with_for_update(skip_locked=True)
    )
    return result.scalar_one_or_none()


async def reconcile_reminder_accounts(
    session_factory: async_sessionmaker[AsyncSession],
    account_uids: list[UUID],
    *,
    now: datetime | None = None,
) -> tuple[int, int]:
    synced = 0
    failed = 0

    for account_uid in account_uids:
        async with session_factory() as db:
            try:
                await sync_activity_reminders(db, account_uid, now=now)
                await sync_friend_birthdays(db, account_uid, now=now)
                synced += 1
            except HTTPException as exc:
                await db.rollback()
                failed += 1
                logger.warning(
                    "Reminder reconciliation skipped account %s: %s",
                    account_uid,
                    getattr(exc, "detail", exc),
                )
            except Exception:
                await db.rollback()
                failed += 1
                logger.exception("Reminder reconciliation failed for account %s", account_uid)

    return synced, failed


async def run_reminder_worker(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    batch_size: int = DEFAULT_WORKER_BATCH_SIZE,
    max_batches: int = DEFAULT_MAX_BATCHES,
    now: datetime | None = None,
) -> ReminderWorkerStats:
    """Run a bounded, fair reconciliation window.

    A durable cursor is protected by a PostgreSQL row lock. If another scheduler
    invocation already owns the row, this run exits without work. Cursor progress
    is committed only after the bounded run finishes; a crash therefore repeats
    the previous window, which is safe because occurrence/notification writes are
    idempotent at the database layer.
    """
    bounded_batch_size = max(1, min(int(batch_size), MAX_WORKER_BATCH_SIZE))
    bounded_max_batches = max(1, min(int(max_batches), MAX_WORKER_BATCHES))
    stats = ReminderWorkerStats()

    async with session_factory() as state_db:
        worker_state = await lock_worker_state(state_db)
        if worker_state is None:
            logger.info("Reminder worker skipped: another invocation owns the cursor lock")
            return stats

        stats.acquired = True
        cursor = worker_state.cursor_account_uid

        for _ in range(bounded_max_batches):
            async with session_factory() as index_db:
                account_uids = await reminder_account_page(
                    index_db,
                    after_uid=cursor,
                    limit=bounded_batch_size,
                )

            if not account_uids:
                worker_state.cursor_account_uid = None
                worker_state.updated_at = datetime.utcnow()
                stats.wrapped = cursor is not None
                break

            stats.batches += 1
            stats.accounts_seen += len(account_uids)
            synced, failed = await reconcile_reminder_accounts(
                session_factory,
                account_uids,
                now=now,
            )
            stats.accounts_synced += synced
            stats.accounts_failed += failed

            cursor = account_uids[-1]
            worker_state.cursor_account_uid = cursor
            worker_state.updated_at = datetime.utcnow()

            if len(account_uids) < bounded_batch_size:
                worker_state.cursor_account_uid = None
                stats.wrapped = True
                break

        await state_db.commit()

    return stats
