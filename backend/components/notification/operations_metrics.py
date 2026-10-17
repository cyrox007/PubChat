from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
import os

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from components.notification.model import ExternalDeliveryLedger, NativePushDevice, WebPushSubscription
from settings import config


DELIVERY_CHANNELS = ("email", "web_push", "native_push")


def _age_seconds(now: datetime, value: datetime | None) -> int:
    if value is None:
        return 0
    return max(0, int((now - value).total_seconds()))


async def external_delivery_metrics(
    db: AsyncSession,
    *,
    window_hours: int = 24,
) -> dict:
    """Aggregate privacy-safe email/Web/native push delivery health."""
    window_hours = max(1, min(720, int(window_hours)))
    now = datetime.utcnow()
    cutoff = now - timedelta(hours=window_hours)

    status_rows = (
        await db.execute(
            select(
                ExternalDeliveryLedger.channel,
                ExternalDeliveryLedger.status,
                func.count(ExternalDeliveryLedger.uid),
            )
            .where(ExternalDeliveryLedger.updated_at >= cutoff)
            .group_by(ExternalDeliveryLedger.channel, ExternalDeliveryLedger.status)
        )
    ).all()
    status_counts: dict[str, dict[str, int]] = defaultdict(dict)
    for channel, status, count in status_rows:
        status_counts[str(channel)][str(status)] = int(count or 0)

    failure_rows = (
        await db.execute(
            select(
                ExternalDeliveryLedger.channel,
                ExternalDeliveryLedger.failure_class,
                func.count(ExternalDeliveryLedger.uid),
            )
            .where(
                ExternalDeliveryLedger.updated_at >= cutoff,
                ExternalDeliveryLedger.failure_class.is_not(None),
            )
            .group_by(ExternalDeliveryLedger.channel, ExternalDeliveryLedger.failure_class)
        )
    ).all()
    failure_counts: dict[str, dict[str, int]] = defaultdict(dict)
    for channel, failure_class, count in failure_rows:
        failure_counts[str(channel)][str(failure_class)] = int(count or 0)

    channels: dict[str, dict] = {}
    attention_reasons: list[str] = []
    backlog_limits = {
        "email": config.EXTERNAL_DELIVERY_EMAIL_BACKLOG_ALERT_SECONDS,
        "web_push": config.EXTERNAL_DELIVERY_WEB_PUSH_BACKLOG_ALERT_SECONDS,
        "native_push": max(
            60,
            min(3600, int(os.getenv("EXTERNAL_DELIVERY_NATIVE_PUSH_BACKLOG_ALERT_SECONDS", "300"))),
        ),
    }

    for channel in DELIVERY_CHANNELS:
        due_filter = (
            ExternalDeliveryLedger.channel == channel,
            ExternalDeliveryLedger.status == "pending",
            or_(
                ExternalDeliveryLedger.next_attempt_at.is_(None),
                ExternalDeliveryLedger.next_attempt_at <= now,
            ),
        )
        pending_count = int(
            (
                await db.execute(
                    select(func.count(ExternalDeliveryLedger.uid)).where(
                        ExternalDeliveryLedger.channel == channel,
                        ExternalDeliveryLedger.status == "pending",
                    )
                )
            ).scalar_one()
            or 0
        )
        due_count, oldest_due_at = (
            await db.execute(
                select(
                    func.count(ExternalDeliveryLedger.uid),
                    func.min(ExternalDeliveryLedger.created_at),
                ).where(*due_filter)
            )
        ).one()
        due_count = int(due_count or 0)
        oldest_due_age_seconds = _age_seconds(now, oldest_due_at)

        processing_count = int(
            (
                await db.execute(
                    select(func.count(ExternalDeliveryLedger.uid)).where(
                        ExternalDeliveryLedger.channel == channel,
                        ExternalDeliveryLedger.status == "processing",
                    )
                )
            ).scalar_one()
            or 0
        )
        expired_claim_count = int(
            (
                await db.execute(
                    select(func.count(ExternalDeliveryLedger.uid)).where(
                        ExternalDeliveryLedger.channel == channel,
                        ExternalDeliveryLedger.status == "processing",
                        or_(
                            ExternalDeliveryLedger.claim_expires_at.is_(None),
                            ExternalDeliveryLedger.claim_expires_at <= now,
                        ),
                    )
                )
            ).scalar_one()
            or 0
        )
        retry_pressure_count = int(
            (
                await db.execute(
                    select(func.count(ExternalDeliveryLedger.uid)).where(
                        ExternalDeliveryLedger.channel == channel,
                        ExternalDeliveryLedger.updated_at >= cutoff,
                        ExternalDeliveryLedger.attempt_count > 1,
                    )
                )
            ).scalar_one()
            or 0
        )
        delivered_count = int(
            (
                await db.execute(
                    select(func.count(ExternalDeliveryLedger.uid)).where(
                        ExternalDeliveryLedger.channel == channel,
                        ExternalDeliveryLedger.delivered_at.is_not(None),
                        ExternalDeliveryLedger.delivered_at >= cutoff,
                    )
                )
            ).scalar_one()
            or 0
        )
        failed_count = int(
            (
                await db.execute(
                    select(func.count(ExternalDeliveryLedger.uid)).where(
                        ExternalDeliveryLedger.channel == channel,
                        ExternalDeliveryLedger.failed_at.is_not(None),
                        ExternalDeliveryLedger.failed_at >= cutoff,
                    )
                )
            ).scalar_one()
            or 0
        )

        backlog_limit = backlog_limits[channel]
        backlog_stale = bool(due_count and oldest_due_age_seconds > backlog_limit)
        if backlog_stale:
            attention_reasons.append(f"{channel}.due_backlog_age_exceeded")
        if expired_claim_count:
            attention_reasons.append(f"{channel}.expired_processing_claims")

        channels[channel] = {
            "status_counts": dict(status_counts.get(channel, {})),
            "failure_class_counts": dict(failure_counts.get(channel, {})),
            "pending_count": pending_count,
            "due_count": due_count,
            "oldest_due_age_seconds": oldest_due_age_seconds,
            "backlog_alert_seconds": backlog_limit,
            "backlog_stale": backlog_stale,
            "processing_count": processing_count,
            "expired_claim_count": expired_claim_count,
            "retry_pressure_count": retry_pressure_count,
            "delivered_count": delivered_count,
            "failed_count": failed_count,
        }

    subscription_count = int(
        (await db.execute(select(func.count(WebPushSubscription.uid)))).scalar_one() or 0
    )
    active_native_device_count = int(
        (
            await db.execute(
                select(func.count(NativePushDevice.uid)).where(NativePushDevice.revoked_at.is_(None))
            )
        ).scalar_one()
        or 0
    )

    return {
        "window_hours": window_hours,
        "healthy": not attention_reasons,
        "attention_reasons": attention_reasons,
        "channels": channels,
        "web_push_subscription_count": subscription_count,
        "native_push_active_device_count": active_native_device_count,
        "privacy": {
            "contains_account_ids": False,
            "contains_destination_addresses": False,
            "contains_push_endpoints": False,
            "contains_native_push_tokens": False,
            "contains_message_content": False,
        },
    }
