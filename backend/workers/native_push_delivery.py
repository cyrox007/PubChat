import argparse
import asyncio
import logging

# Load backend/.env before native push modules resolve FCM os.environ values in
# this standalone worker process.
from settings import config  # noqa: F401

from components.model_registry import ensure_models_registered
from components.notification.native_push import FCMProvider, NATIVE_PUSH_BATCH_SIZE, run_native_push_worker
from components.notification.native_push_config import validate_fcm_configuration
from components.realtime import realtime_service
from database import Database
from utils.logger import setup_logger
from utils.observability import log_structured


logger = setup_logger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Deliver privacy-minimal native PubChat push through direct FCM HTTP v1.",
    )
    parser.add_argument(
        "--max-deliveries",
        type=int,
        default=NATIVE_PUSH_BATCH_SIZE,
        help="Maximum durable native push delivery records processed in this run (1..250).",
    )
    parser.add_argument(
        "--check-config",
        action="store_true",
        help="Validate FCM configuration locally without sending push or scanning delivery state.",
    )
    return parser


def check_configuration() -> int:
    result = validate_fcm_configuration()
    if result["valid"]:
        logger.info("Direct FCM HTTP v1 configuration preflight: OK")
        return 0
    logger.error(
        "Direct FCM HTTP v1 configuration preflight failed: %s",
        ",".join(result["errors"]) or "fcm_configuration_invalid",
    )
    return 2


async def run(max_deliveries: int) -> int:
    ensure_models_registered()
    configuration = validate_fcm_configuration()
    if not configuration["valid"]:
        logger.error(
            "Direct FCM HTTP v1 credentials are not production-ready: %s",
            ",".join(configuration["errors"]) or "fcm_configuration_invalid",
        )
        return 2
    provider = FCMProvider()
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
    if args.check_config:
        return check_configuration()
    return asyncio.run(run(max(1, min(int(args.max_deliveries), 250))))


if __name__ == "__main__":
    raise SystemExit(main())
