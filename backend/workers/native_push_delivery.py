import argparse
import asyncio
import logging

from components.model_registry import ensure_models_registered
from components.notification.native_push import FCMProvider, NATIVE_PUSH_BATCH_SIZE, run_native_push_worker
from components.realtime import realtime_service
from database import Database
from utils.logger import setup_logger
from utils.observability import log_structured


logger = setup_logger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deliver privacy-minimal native PubChat push through FCM (Android) and APNs (iOS).",
    )
    parser.add_argument(
        "--max-deliveries",
        type=int,
        default=NATIVE_PUSH_BATCH_SIZE,
        help="Maximum durable native push delivery records processed in this run (1..250).",
    )
    return parser


async def run(max_deliveries: int) -> int:
    ensure_models_registered()
    provider = FCMProvider()
    if not provider.configured:
        logger.error("Neither direct FCM nor APNs credentials are configured")
        return 2
    try:
        stats = await run_native_push_worker(
            Database.sessionmaker(),
            provider=provider,
            max_deliveries=max_deliveries,
        )
        log_structured(
            logger,
            logging.INFO,
            "external_delivery.native_push.delivery_complete",
            infrastructure_ready=stats.infrastructure_ready,
            accounts_scanned=stats.accounts_scanned,
            queued=stats.queued,
            claimed=stats.claimed,
            delivered=stats.delivered,
            retried=stats.retried,
            failed=stats.failed,
            suppressed=stats.suppressed,
            terminal_devices_revoked=stats.terminal_devices_revoked,
        )
        if not stats.infrastructure_ready:
            return 2
        return 1 if stats.failed else 0
    finally:
        await realtime_service.stop()
        await Database.dispose()


def main() -> int:
    args = build_parser().parse_args()
    return asyncio.run(run(max(1, min(int(args.max_deliveries), 250))))


if __name__ == "__main__":
    raise SystemExit(main())
