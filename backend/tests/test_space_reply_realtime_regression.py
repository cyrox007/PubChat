"""Regression: replies to another Space member must not kill a realtime socket."""
import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import WebSocketDisconnect

from components.message.model import Message
from views.rooms import ws_handlers as room_ws


class SpaceReplyRealtimeTests(unittest.TestCase):
    def test_reply_parent_author_is_eager_loaded_before_formatting(self):
        async def scenario():
            room_uid, author_uid, quoted_author_uid, reply_uid = (
                uuid4(), uuid4(), uuid4(), uuid4()
            )
            writer = MagicMock()
            writer.flush = AsyncMock()
            writer.commit = AsyncMock()
            writer.refresh = AsyncMock(
                side_effect=lambda message: setattr(message, "uid", reply_uid)
            )
            quoted = SimpleNamespace(
                uid=uuid4(), text="from peer", author_uid=quoted_author_uid,
                author=SimpleNamespace(username="peer"),
            )
            saved = SimpleNamespace(
                uid=reply_uid, text="answer", content_type="text",
                media_metadata=None, author_uid=author_uid, room_uid=room_uid,
                author=SimpleNamespace(username="writer", avatar=None),
                reply_to=quoted, created_at=__import__("datetime").datetime.utcnow(),
            )
            result = MagicMock()
            result.scalar_one.return_value = saved
            writer.execute = AsyncMock(return_value=result)
            value = await Message.create_message(writer, {
                "room_uid": str(room_uid), "sender_uid": str(author_uid),
                "content": "answer", "reply_to_uid": str(quoted.uid),
            })
            self.assertEqual(value["reply_to"]["sender"]["name"], "peer")
            self.assertEqual(value["reply_to"]["uid"], str(quoted.uid))
            statement = str(writer.execute.await_args.args[0]).lower()
            # An eager join to the parent and the parent's user avoids ORM
            # lazy IO during synchronous message formatting (MissingGreenlet).
            self.assertIn("left outer join messages", statement)
            self.assertGreaterEqual(statement.count("join users"), 2)
            writer.flush.assert_awaited_once()
            writer.commit.assert_awaited_once()
        asyncio.run(scenario())

    def test_foreign_room_reply_is_rejected_without_publishing(self):
        async def scenario():
            room_uid, user_uid = uuid4(), uuid4()
            db = MagicMock()
            db.get = AsyncMock(return_value=SimpleNamespace(
                room_uid=uuid4(), content_type="text",
            ))
            ws = SimpleNamespace(send_json=AsyncMock())
            with patch.object(room_ws, "_claim_client_event", new_callable=AsyncMock) as claim:
                await room_ws.handle_text_message({
                    "content": "no leak", "reply_to_uid": str(uuid4()),
                    "frontId": "bad-target",
                }, room_uid, user_uid, db, ws)
                claim.assert_not_awaited()
            ws.send_json.assert_awaited_once()
            self.assertEqual(ws.send_json.await_args.args[0]["error_type"], "reply_target_unavailable")

        asyncio.run(scenario())

    def test_normal_reply_is_broadcast_with_original_front_id(self):
        async def scenario():
            room_uid, user_uid, parent_uid = uuid4(), uuid4(), uuid4()
            db = MagicMock()
            db.get = AsyncMock(return_value=SimpleNamespace(
                uid=parent_uid, room_uid=room_uid, content_type="text",
            ))
            ws = SimpleNamespace(send_json=AsyncMock())
            frame = {"type": "message", "uid": str(uuid4()), "reply_to": {
                "uid": str(parent_uid), "sender": {"name": "other person"},
            }}
            with patch.object(room_ws, "_claim_client_event", new_callable=AsyncMock, return_value=True), \
                 patch.object(room_ws, "inspect_plaintext_write", new_callable=AsyncMock), \
                 patch.object(Message, "create_message", new_callable=AsyncMock, return_value=frame) as save, \
                 patch.object(room_ws, "_deliver_saved_room_message", new_callable=AsyncMock) as deliver:
                await room_ws.handle_text_message({
                    "content": "hello", "reply_to_uid": str(parent_uid),
                    "frontId": "reply-1",
                }, room_uid, user_uid, db, ws)
                self.assertEqual(save.await_args.args[1] if save.await_args.kwargs else save.await_args.args[1], {
                    "content": "hello", "content_type": "text", "frontId": "reply-1",
                    "sender_uid": str(user_uid), "room_uid": str(room_uid),
                    "reply_to_uid": str(parent_uid), "timestamp": save.await_args.args[1]["timestamp"],
                })
                deliver.assert_awaited_once_with(
                    room_uid, user_uid, frame, ws,
                )
                ws.send_json.assert_not_awaited()
        asyncio.run(scenario())

    def test_one_failed_frame_does_not_close_following_replies(self):
        async def scenario():
            room_uid, user_uid = uuid4(), uuid4()
            ws = SimpleNamespace(receive_json=AsyncMock(side_effect=[
                {"type": "message", "content_type": "text", "frontId": "one"},
                {"type": "message", "content_type": "text", "frontId": "two"},
                WebSocketDisconnect(code=1000),
            ]), send_json=AsyncMock())
            db = MagicMock()
            db.rollback = AsyncMock()
            with patch.object(room_ws, "release_realtime_session", new_callable=AsyncMock), \
                 patch.object(room_ws.manager, "touch_connection", new_callable=AsyncMock), \
                 patch.object(room_ws.manager, "update_user_activity", new_callable=AsyncMock), \
                 patch.object(room_ws, "_enforce_capability", new_callable=AsyncMock, return_value=True), \
                 patch.object(room_ws, "_rate_limit_message", new_callable=AsyncMock, return_value=True), \
                 patch.object(room_ws, "handle_text_message", new_callable=AsyncMock, side_effect=[RuntimeError("db"), None]) as send:
                with self.assertRaises(WebSocketDisconnect):
                    await room_ws.process_incoming_messages(ws, room_uid, user_uid, db)
                self.assertEqual(send.await_count, 2)
                db.rollback.assert_awaited_once()
                self.assertEqual(ws.send_json.await_args.args[0], {
                    "type": "error", "error_type": "space_message_failed", "frontId": "one",
                })
        asyncio.run(scenario())

    def test_committed_reply_is_acknowledged_locally_even_if_redis_publish_fails(self):
        async def scenario():
            room_uid, author_uid, parent_uid = uuid4(), uuid4(), uuid4()
            db = MagicMock()
            db.get = AsyncMock(return_value=SimpleNamespace(
                uid=parent_uid, room_uid=room_uid, content_type="text",
            ))
            websocket = SimpleNamespace(send_json=AsyncMock())
            frame = {"type": "message", "uid": str(uuid4()),
                     "reply_to": {"uid": str(parent_uid)}}
            context = MagicMock()
            context.__aenter__ = AsyncMock(return_value=MagicMock())
            context.__aexit__ = AsyncMock(return_value=False)
            with patch.object(room_ws, "_claim_client_event", new_callable=AsyncMock, return_value=True), \
                 patch.object(room_ws, "_release_client_event", new_callable=AsyncMock) as release, \
                 patch.object(room_ws, "inspect_plaintext_write", new_callable=AsyncMock), \
                 patch.object(Message, "create_message", new_callable=AsyncMock, return_value=frame) as save, \
                 patch.object(room_ws.manager, "broadcast_to_room", new_callable=AsyncMock,
                              side_effect=RuntimeError("redis bus offline")), \
                 patch.object(room_ws.manager, "send_to_specific_user", new_callable=AsyncMock) as fallback, \
                 patch.object(room_ws.Database, "sessionmaker", return_value=lambda: context), \
                 patch.object(room_ws, "_notify_online_members", new_callable=AsyncMock,
                              side_effect=RuntimeError("notification worker offline")):
                await room_ws.handle_text_message(
                    {"content": "hello", "reply_to_uid": str(parent_uid), "frontId": "safari-reply"},
                    room_uid, author_uid, db, websocket,
                )
            save.assert_awaited_once()
            fallback.assert_awaited_once_with(websocket, frame)
            self.assertEqual(frame["frontId"], "safari-reply")
            release.assert_not_awaited()
            websocket.send_json.assert_not_awaited()
        asyncio.run(scenario())

    def test_stalled_secondary_transports_do_not_hold_room_message_loop(self):
        async def scenario():
            room_uid, sender_uid = uuid4(), uuid4()
            websocket = SimpleNamespace(send_json=AsyncMock())
            saved = {"type": "message", "uid": str(uuid4()), "frontId": "safari-2"}
            context = MagicMock()
            context.__aenter__ = AsyncMock(return_value=MagicMock())
            context.__aexit__ = AsyncMock(return_value=False)

            async def never_returns(*_args, **_kwargs):
                await asyncio.Event().wait()

            with patch.object(room_ws, "POST_COMMIT_DELIVERY_TIMEOUT_SECONDS", 0.025), \
                 patch.object(room_ws.manager, "broadcast_to_room", new_callable=AsyncMock,
                              side_effect=never_returns), \
                 patch.object(room_ws.manager, "send_to_specific_user", new_callable=AsyncMock) as fallback, \
                 patch.object(room_ws.Database, "sessionmaker", return_value=lambda: context), \
                 patch.object(room_ws, "_notify_online_members", new_callable=AsyncMock,
                              side_effect=never_returns):
                await asyncio.wait_for(room_ws._deliver_saved_room_message(
                    room_uid, sender_uid, saved, websocket,
                ), timeout=0.25)
            fallback.assert_awaited_once_with(websocket, saved)
        asyncio.run(scenario())

    def test_online_notifications_are_best_effort_after_message_commit(self):
        async def scenario():
            db = MagicMock()
            db.rollback = AsyncMock()
            with patch.object(room_ws, "queue_space_reply", new_callable=AsyncMock, return_value=None), \
                 patch.object(room_ws, "notify_online_space_members", new_callable=AsyncMock, side_effect=RuntimeError("notifications down")):
                await room_ws._notify_online_members(db, uuid4(), uuid4(), {
                    "type": "message", "uid": str(uuid4()),
                })
                db.rollback.assert_awaited_once()
        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
