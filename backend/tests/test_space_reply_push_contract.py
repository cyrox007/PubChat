import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

from components.notification.model import UserNotification
from components.notification.native_push import (
    build_messenger_native_push_payload, native_unread_dedupe_key,
)
from components.notification.space_reply_delivery import (
    SPACE_REPLY_KIND, queue_space_reply, space_reply_claim_payload,
    space_reply_push_payload,
)
from components.notification.web_push import build_messenger_push_payload


class SpaceReplyPushContractTests(unittest.TestCase):
    def test_reply_payload_is_targeted_and_content_free(self):
        room_uid = uuid4()
        payload = space_reply_push_payload(room_uid)
        self.assertEqual(payload["type"], "space_reply")
        self.assertEqual(payload["url"], f"/spaces/{room_uid}")
        self.assertEqual(payload["room_uid"], str(room_uid))
        for secret in ("sender", "username", "message", "content", "ciphertext", "attachment"):
            self.assertNotIn(secret, payload)
        self.assertEqual(UserNotification.__tablename__, "user_notifications")
        self.assertLessEqual(len(payload["tag"]), 120)

    def test_generic_dm_push_is_still_privacy_safe(self):
        for payload in (build_messenger_native_push_payload(), build_messenger_push_payload()):
            self.assertEqual(payload["url"], "/messenger")
            self.assertNotIn("sender", payload)
            self.assertNotIn("content", payload)

    def test_native_dedupe_key_is_stable_per_unread_uid(self):
        uid = UUID("11111111-1111-4111-8111-111111111111")
        self.assertEqual(native_unread_dedupe_key(uid), f"unread-dm:{uid}")
        self.assertEqual(native_unread_dedupe_key(uid), native_unread_dedupe_key(uid))
        self.assertNotEqual(native_unread_dedupe_key(uid), native_unread_dedupe_key(uuid4()))

    def test_no_reply_and_malformed_source_do_not_write_or_notify(self):
        async def go():
            session = SimpleNamespace(get=AsyncMock(), execute=AsyncMock())
            room, sender = uuid4(), uuid4()
            self.assertIsNone(await queue_space_reply(
                session, room_uid=room, sender_legacy_uid=sender,
                formatted_message={"uid": str(uuid4())},
            ))
            self.assertIsNone(await queue_space_reply(
                session, room_uid=room, sender_legacy_uid=sender,
                formatted_message={"uid": "invalid", "reply_to": {"uid": str(uuid4())}},
            ))
            session.get.assert_not_awaited()
            session.execute.assert_not_awaited()
        asyncio.run(go())

    def test_cross_room_or_self_reply_never_routes_to_an_account(self):
        async def go():
            room, sender = uuid4(), uuid4()
            async def check(parent):
                session = SimpleNamespace(get=AsyncMock(return_value=parent), execute=AsyncMock())
                result = await queue_space_reply(
                    session, room_uid=room, sender_legacy_uid=sender,
                    formatted_message={
                        "uid": str(uuid4()), "reply_to": {"uid": str(uuid4())},
                    },
                )
                self.assertIsNone(result)
                session.execute.assert_not_awaited()
            await check(SimpleNamespace(room_uid=uuid4(), author_uid=uuid4()))
            await check(SimpleNamespace(room_uid=room, author_uid=sender))
        asyncio.run(go())

    def test_unbound_claim_never_reads_private_notifications(self):
        async def go():
            session = SimpleNamespace(get=AsyncMock())
            account = uuid4()
            for key in ("messenger:foo", "space-reply:bad-uid"):
                self.assertIsNone(await space_reply_claim_payload(session, key, account))
            session.get.assert_not_awaited()
        asyncio.run(go())


if __name__ == "__main__":
    unittest.main()
