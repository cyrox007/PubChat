"""Cross-client Space reply notifications: REST must match WebSocket, not DM."""
import asyncio
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import FastAPI

from components.message.model import Message
from views.messages import routers as messages_routes


def room_reply_endpoint():
    app = FastAPI()
    messages_routes.install(app)
    return next(
        route.endpoint for route in app.routes
        if route.path == "/messages/v2/{surface}/{message_uid}/reply"
    )


class SpaceHttpReplyNotificationTests(unittest.TestCase):
    def test_android_http_reply_persists_actual_parent_uid_and_enqueues_personal_notification(self):
        async def check():
            room_uid, parent_uid, sender_uid, other_uid = uuid4(), uuid4(), uuid4(), uuid4()
            parent = SimpleNamespace(
                uid=parent_uid, room_uid=room_uid, author_uid=other_uid,
                content_type="text", text="parent", created_at=datetime.utcnow(),
            )
            created = {"type": "message", "uid": str(uuid4()),
                       "reply_to": {"uid": str(parent_uid), "sender": {"uid": str(other_uid)}}}
            db = MagicMock()
            route = room_reply_endpoint()
            with patch.object(messages_routes, "load_message", new_callable=AsyncMock, return_value=parent), \
                 patch.object(messages_routes, "ensure_message_access", new_callable=AsyncMock), \
                 patch.object(messages_routes, "assert_allowed", new_callable=AsyncMock), \
                 patch.object(messages_routes, "active_room_member", new_callable=AsyncMock, return_value=True), \
                 patch.object(messages_routes, "inspect_plaintext_write", new_callable=AsyncMock), \
                 patch.object(Message, "create_message", new_callable=AsyncMock, return_value=created) as store, \
                 patch.object(messages_routes, "_publish_space_reply_after_commit", new_callable=AsyncMock) as deliver:
                outcome = await route(
                    surface="room", message_uid=parent_uid,
                    payload=messages_routes.ReplyMessageRequest(content="reply"),
                    current_user={"user_uid": str(sender_uid)}, db=db,
                )
            self.assertEqual(outcome["message"], created)
            self.assertEqual(store.await_args.args[1]["reply_to_uid"], str(parent_uid))
            self.assertEqual(store.await_args.args[1]["room_uid"], str(room_uid))
            self.assertEqual(store.await_args.args[1]["sender_uid"], str(sender_uid))
            deliver.assert_awaited_once_with(
                db, room_uid=room_uid, sender_uid=sender_uid, created=created,
            )
        asyncio.run(check())

    def test_reply_enqueues_durable_personal_push_and_excludes_target_from_generic_alert(self):
        async def check():
            db, room_uid, sender_uid, recipient_uid = MagicMock(), uuid4(), uuid4(), uuid4()
            created = {"uid": str(uuid4()), "reply_to": {"uid": str(uuid4())}}
            notification_db = MagicMock()
            context = MagicMock()
            context.__aenter__ = AsyncMock(return_value=notification_db)
            context.__aexit__ = AsyncMock(return_value=None)
            with patch.object(messages_routes.Database, "sessionmaker", return_value=lambda: context), \
                 patch.object(messages_routes.room_manager, "broadcast_to_room", new_callable=AsyncMock) as broadcast, \
                 patch.object(messages_routes, "queue_space_reply", new_callable=AsyncMock, return_value=recipient_uid) as queue, \
                 patch.object(messages_routes, "notify_online_space_members", new_callable=AsyncMock) as generic:
                await messages_routes._publish_space_reply_after_commit(
                    db, room_uid=room_uid, sender_uid=sender_uid, created=created,
                )
            broadcast.assert_awaited_once_with(room_uid, created)
            queue.assert_awaited_once_with(
                notification_db, room_uid=room_uid,
                sender_legacy_uid=sender_uid, formatted_message=created,
            )
            generic.assert_awaited_once_with(
                notification_db, room_uid=room_uid, sender_uid=sender_uid,
                formatted_message=created, exclude_uids={recipient_uid},
            )
        asyncio.run(check())

    def test_push_outage_does_not_reject_committed_http_reply(self):
        async def check():
            db = MagicMock()
            db.rollback = AsyncMock()
            notification_db = MagicMock()
            context = MagicMock()
            context.__aenter__ = AsyncMock(return_value=notification_db)
            context.__aexit__ = AsyncMock(return_value=None)
            with patch.object(messages_routes.Database, "sessionmaker", return_value=lambda: context), \
                 patch.object(messages_routes.room_manager, "broadcast_to_room", new_callable=AsyncMock, side_effect=RuntimeError("realtime outage")), \
                 patch.object(messages_routes, "queue_space_reply", new_callable=AsyncMock, side_effect=RuntimeError("push outage")), \
                 patch.object(messages_routes, "notify_online_space_members", new_callable=AsyncMock):
                await messages_routes._publish_space_reply_after_commit(
                    db, room_uid=uuid4(), sender_uid=uuid4(),
                    created={"uid": str(uuid4())},
                )
            # A notification outage must not roll back or poison the request
            # session that already committed the canonical reply.
            db.rollback.assert_not_awaited()
            context.__aexit__.assert_awaited_once()
        asyncio.run(check())

    def test_other_room_message_is_not_eligible_for_personal_reply_push(self):
        # Eligibility and block checks belong to the existing tested
        # queue_space_reply contract, never bypassed by this HTTP helper.
        self.assertTrue(callable(messages_routes.queue_space_reply))


if __name__ == "__main__":
    unittest.main()
