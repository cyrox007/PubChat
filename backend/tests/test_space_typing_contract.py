import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException

from views.rooms.ws_typing import TypingAwareWebSocket, relay_typing


class SpaceTypingContractTests(unittest.IsolatedAsyncioTestCase):
    @patch("views.rooms.ws_typing.room_manager.broadcast_to_room_except", new_callable=AsyncMock)
    @patch("views.rooms.ws_typing.realtime_service.allow_action", new_callable=AsyncMock)
    @patch("views.rooms.ws_typing.assert_allowed", new_callable=AsyncMock)
    async def test_typing_is_ephemeral_scoped_and_excludes_sender(
        self,
        assert_allowed,
        allow_action,
        broadcast,
    ):
        room_uid = uuid4()
        user_uid = uuid4()
        allow_action.return_value = True

        await relay_typing(room_uid, user_uid, MagicMock(), True)

        assert_allowed.assert_awaited_once()
        allow_action.assert_awaited_once_with(
            user_uid=user_uid,
            bucket=f"space-typing:{room_uid}",
            limit=20,
            window_seconds=10,
        )
        broadcast.assert_awaited_once_with(
            room_uid,
            {
                "type": "typing",
                "user_uid": str(user_uid),
                "active": True,
                "expires_in": 5,
            },
            exclude_user=user_uid,
        )

    @patch("views.rooms.ws_typing.room_manager.broadcast_to_room_except", new_callable=AsyncMock)
    @patch("views.rooms.ws_typing.realtime_service.allow_action", new_callable=AsyncMock)
    @patch("views.rooms.ws_typing.assert_allowed", new_callable=AsyncMock)
    async def test_restricted_user_cannot_emit_typing(
        self,
        assert_allowed,
        allow_action,
        broadcast,
    ):
        assert_allowed.side_effect = HTTPException(
            status_code=403,
            detail={"error_type": "capability_restricted"},
        )

        await relay_typing(uuid4(), uuid4(), MagicMock(), True)

        allow_action.assert_not_awaited()
        broadcast.assert_not_awaited()

    @patch("views.rooms.ws_typing.room_manager.broadcast_to_room_except", new_callable=AsyncMock)
    @patch("views.rooms.ws_typing.realtime_service.allow_action", new_callable=AsyncMock)
    async def test_non_boolean_typing_payload_is_ignored(self, allow_action, broadcast):
        await relay_typing(uuid4(), uuid4(), MagicMock(), "yes")

        allow_action.assert_not_awaited()
        broadcast.assert_not_awaited()

    @patch("views.rooms.ws_typing.relay_typing", new_callable=AsyncMock)
    @patch("views.rooms.ws_typing.room_manager.touch_connection", new_callable=AsyncMock)
    async def test_proxy_consumes_typing_and_returns_next_canonical_frame(
        self,
        touch_connection,
        relay,
    ):
        websocket = MagicMock()
        websocket.receive_json = AsyncMock(
            side_effect=[
                {"type": "typing", "active": True},
                {"type": "heartbeat"},
            ]
        )
        room_uid = uuid4()
        user_uid = uuid4()
        proxy = TypingAwareWebSocket(websocket, room_uid, user_uid, AsyncMock())

        result = await proxy.receive_json()

        self.assertEqual(result, {"type": "heartbeat"})
        touch_connection.assert_awaited_once_with(proxy)
        relay.assert_awaited_once_with(room_uid, user_uid, proxy._db_session, True)


if __name__ == "__main__":
    unittest.main()
