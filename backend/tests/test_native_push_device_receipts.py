import asyncio
import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from components.notification.model import NativePushDeliveryReceipt
from components.notification.native_push import (
    NativePushClaim, _receipt_status, _mark_receipt,
)


class NativePushReceiptContractTests(unittest.TestCase):
    def test_receipt_models_track_target_without_message_text(self):
        cols = set(NativePushDeliveryReceipt.__table__.c.keys())
        self.assertTrue({"ledger_uid", "device_uid", "status", "provider_message_id", "failure_class"} <= cols)
        for forbidden in ("message_text", "content", "ciphertext", "sender", "token", "access_token"):
            self.assertNotIn(forbidden, cols)
        keys = {constraint.name for constraint in NativePushDeliveryReceipt.__table__.constraints}
        self.assertIn("uq_native_push_ledger_device", keys)

    def test_already_delivered_receipts_are_queried_per_device(self):
        async def run():
            ledger, device = uuid4(), uuid4()
            rows = SimpleNamespace(scalar_one_or_none=lambda: "delivered")
            db = SimpleNamespace(execute=AsyncMock(return_value=rows))
            self.assertEqual(await _receipt_status(db, ledger, device), "delivered")
            stmt = db.execute.call_args.args[0]
            compiled = str(stmt)
            self.assertIn("native_push_delivery_receipts.ledger_uid", compiled)
            self.assertIn("native_push_delivery_receipts.device_uid", compiled)
        asyncio.run(run())

    def test_stale_claim_fails_closed_without_recording_result(self):
        async def run():
            claim = NativePushClaim(uuid4(), uuid4(), "stale", 1, "unread-dm:any")
            db = SimpleNamespace(
                execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None)),
                rollback=AsyncMock(), commit=AsyncMock(), add=lambda _: None,
            )
            confirmed = await _mark_receipt(db, claim, uuid4(), status="delivered", provider_id="os-success")
            self.assertFalse(confirmed)
            db.rollback.assert_awaited_once()
            db.commit.assert_not_awaited()
        asyncio.run(run())

    def test_only_explicit_terminal_states_are_persisted(self):
        async def run():
            claim = NativePushClaim(uuid4(), uuid4(), "token", 1, "unread-dm:any")
            with self.assertRaises(ValueError):
                await _mark_receipt(SimpleNamespace(), claim, uuid4(), status="unknown")
        asyncio.run(run())

    def test_receipt_is_written_before_account_ledger_finalization(self):
        # Regression guard for the multi-device partial-ack loss from prior code.
        from components.notification import native_push
        source = inspect.getsource(native_push.run_native_push_worker)
        self.assertIn("_receipt_status(db, claim.uid, target.uid)", source)
        self.assertIn("if already in {\"delivered\", \"terminal\"}", source)
        self.assertLess(source.index("_mark_receipt(db, claim, target.uid, status=\"delivered\""),
                        source.index("if retryable_failure:"))
        self.assertLess(source.index("if retryable_failure:"), source.index("if completed:"))


if __name__ == "__main__":
    unittest.main()
