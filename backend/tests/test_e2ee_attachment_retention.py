import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from components.message.e2ee_attachment_retention import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_ORPHAN_GRACE_HOURS,
    DEFAULT_PENDING_RETENTION_HOURS,
    MAX_BATCH_SIZE,
    _old_orphan_candidates,
    _safe_storage_file,
    orphan_grace_hours,
    pending_retention_hours,
    retention_batch_size,
)


class E2EEAttachmentRetentionTests(unittest.TestCase):
    def test_safe_storage_file_only_accepts_generated_ciphertext_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            valid = "a" * 32 + ".bin"
            self.assertEqual(_safe_storage_file(root, valid), root / valid)
            self.assertIsNone(_safe_storage_file(root, "../escape.bin"))
            self.assertIsNone(_safe_storage_file(root, "notes.txt"))
            self.assertIsNone(_safe_storage_file(root, "A" * 32 + ".bin"))

    def test_orphan_scan_ignores_recent_unrelated_and_symlink_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old_ciphertext = root / ("b" * 32 + ".bin")
            recent_ciphertext = root / ("c" * 32 + ".bin")
            unrelated = root / "keep-me.txt"
            old_ciphertext.write_bytes(b"old")
            recent_ciphertext.write_bytes(b"new")
            unrelated.write_text("not managed", encoding="utf-8")
            old_ts = (datetime.now() - timedelta(hours=48)).timestamp()
            os.utime(old_ciphertext, (old_ts, old_ts))
            os.utime(unrelated, (old_ts, old_ts))

            symlink = root / ("d" * 32 + ".bin")
            try:
                symlink.symlink_to(old_ciphertext)
            except (OSError, NotImplementedError):
                symlink = None

            candidates, skipped = _old_orphan_candidates(
                root,
                cutoff=datetime.now() - timedelta(hours=24),
                limit=10,
            )
            self.assertEqual([path.name for path in candidates], [old_ciphertext.name])
            if symlink is not None:
                self.assertGreaterEqual(skipped, 1)

    def test_retention_environment_values_are_bounded(self):
        with patch.dict(os.environ, {}, clear=False):
            for key in (
                "E2EE_ATTACHMENT_PENDING_RETENTION_HOURS",
                "E2EE_ATTACHMENT_ORPHAN_GRACE_HOURS",
                "E2EE_ATTACHMENT_RETENTION_BATCH_SIZE",
            ):
                os.environ.pop(key, None)
            self.assertEqual(pending_retention_hours(), DEFAULT_PENDING_RETENTION_HOURS)
            self.assertEqual(orphan_grace_hours(), DEFAULT_ORPHAN_GRACE_HOURS)
            self.assertEqual(retention_batch_size(), DEFAULT_BATCH_SIZE)

        with patch.dict(
            os.environ,
            {
                "E2EE_ATTACHMENT_PENDING_RETENTION_HOURS": "0",
                "E2EE_ATTACHMENT_ORPHAN_GRACE_HOURS": "999999",
                "E2EE_ATTACHMENT_RETENTION_BATCH_SIZE": "999999",
            },
            clear=False,
        ):
            self.assertEqual(pending_retention_hours(), 1)
            self.assertEqual(orphan_grace_hours(), 24 * 30)
            self.assertEqual(retention_batch_size(), MAX_BATCH_SIZE)


if __name__ == "__main__":
    unittest.main()
