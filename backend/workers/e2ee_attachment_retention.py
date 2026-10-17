import argparse
import asyncio

from components.message.e2ee_attachment_retention import (
    cleanup_e2ee_attachment_storage,
    orphan_grace_hours,
    pending_retention_hours,
    retention_batch_size,
)
from components.model_registry import ensure_models_registered
from database import Database
from utils.logger import setup_logger


logger = setup_logger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Remove expired pending and orphaned PubChat E2EE attachment ciphertext.",
    )
    parser.add_argument("--batch-size", type=int, default=retention_batch_size())
    parser.add_argument("--pending-hours", type=int, default=pending_retention_hours())
    parser.add_argument("--orphan-hours", type=int, default=orphan_grace_hours())
    parser.add_argument("--dry-run", action="store_true")
    return parser


async def run(*, batch_size: int, pending_hours: int, orphan_hours: int, dry_run: bool) -> int:
    ensure_models_registered()
    try:
        async with Database.sessionmaker()() as db:
            stats = await cleanup_e2ee_attachment_storage(
                db,
                batch_size=batch_size,
                pending_hours=pending_hours,
                orphan_hours=orphan_hours,
                dry_run=dry_run,
            )
        logger.info(
            "E2EE attachment retention complete: dry_run=%s pending_candidates=%s "
            "pending_rows_deleted=%s pending_files_deleted=%s pending_files_missing=%s "
            "orphan_candidates=%s orphan_files_deleted=%s skipped_symlinks=%s failed=%s",
            dry_run,
            stats.pending_candidates,
            stats.pending_rows_deleted,
            stats.pending_files_deleted,
            stats.pending_files_missing,
            stats.orphan_candidates,
            stats.orphan_files_deleted,
            stats.skipped_symlinks,
            stats.failed,
        )
        return 1 if stats.failed else 0
    finally:
        await Database.dispose()


def main() -> int:
    args = build_parser().parse_args()
    return asyncio.run(
        run(
            batch_size=max(1, args.batch_size),
            pending_hours=max(1, args.pending_hours),
            orphan_hours=max(1, args.orphan_hours),
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
