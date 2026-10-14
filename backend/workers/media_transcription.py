import argparse
import asyncio
import logging

from components.model_registry import ensure_models_registered
from components.transcription.service import run_transcription_worker
from components.transcription.settings import transcription_config
from database import Database
from utils.logger import setup_logger
from utils.observability import log_structured


logger = setup_logger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Process PubChat voice/video transcription jobs.")
    parser.add_argument("--batch-size", type=int, default=transcription_config.batch_size)
    return parser


async def run(batch_size: int) -> int:
    ensure_models_registered()
    try:
        stats = await run_transcription_worker(Database.sessionmaker(), batch_size=batch_size)
        log_structured(
            logger,
            logging.INFO,
            "transcription.worker_complete",
            discovered=stats.discovered,
            claimed=stats.claimed,
            completed=stats.completed,
            retried=stats.retried,
            failed=stats.failed,
        )
        return 1 if stats.failed else 0
    finally:
        await Database.dispose()


def main() -> int:
    args = build_parser().parse_args()
    return asyncio.run(run(args.batch_size))


if __name__ == "__main__":
    raise SystemExit(main())
