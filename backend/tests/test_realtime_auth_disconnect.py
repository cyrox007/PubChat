import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from starlette.websockets import WebSocketDisconnect

from views.realtime import ws_auth


def _socket():
    return SimpleNamespace(
        accept=AsyncMock(),
        receive_json=AsyncMock(return_value={"type": "auth", "ticket": "t" * 32}),
        send_json=AsyncMock(),
        close=AsyncMock(),
        state=SimpleNamespace(),
    )


class RealtimeAuthDisconnectTests(unittest.IsolatedAsyncioTestCase):
    async def test_disconnect_while_sending_ready_is_not_an_asgi_failure(self):
        websocket = _socket()
        websocket.send_json.side_effect = WebSocketDisconnect(1006)
        session = AsyncMock()
        with (
            patch.object(ws_auth.realtime_service, "consume_ticket", new_callable=AsyncMock,
                         return_value={"account_uid": str(uuid4())}),
            patch.object(ws_auth.Database, "get_session", new_callable=AsyncMock, return_value=session),
            patch.object(ws_auth, "active_account_access_restriction",
                         new_callable=AsyncMock, return_value=None),
        ):
            self.assertIsNone(await ws_auth.authenticate_websocket(websocket, "room", uuid4()))
            session.close.assert_awaited_once()

    async def test_slow_redis_ticket_cannot_leave_socket_authenticating(self):
        websocket = _socket()

        async def stalled_ticket(**kwargs):
            await asyncio.sleep(10)

        with (
            patch.object(ws_auth.realtime_service, "consume_ticket", side_effect=stalled_ticket),
            patch.object(ws_auth.config, "REALTIME_AUTH_TIMEOUT_SECONDS", 0.01),
        ):
            self.assertIsNone(await ws_auth.authenticate_websocket(websocket, "messenger"))
        self.assertEqual(websocket.close.await_args.kwargs["code"], 1013)

    async def test_slow_db_validation_returns_connection_and_closes_socket(self):
        websocket = _socket()
        session = AsyncMock()

        async def stalled_db(*args, **kwargs):
            await asyncio.sleep(10)

        with (
            patch.object(ws_auth.realtime_service, "consume_ticket", new_callable=AsyncMock,
                         return_value={"account_uid": str(uuid4())}),
            patch.object(ws_auth.Database, "get_session", new_callable=AsyncMock, return_value=session),
            patch.object(ws_auth, "active_account_access_restriction", side_effect=stalled_db),
            patch.object(ws_auth.config, "REALTIME_AUTH_TIMEOUT_SECONDS", 0.01),
        ):
            self.assertIsNone(await ws_auth.authenticate_websocket(websocket, "messenger"))
        self.assertEqual(websocket.close.await_args.kwargs["code"], 1013)
        session.close.assert_awaited_once()

    async def test_redis_failure_is_transient_not_an_unhandled_ws_error(self):
        websocket = _socket()
        with patch.object(
            ws_auth.realtime_service, "consume_ticket",
            new_callable=AsyncMock, side_effect=ConnectionError("redis down"),
        ):
            self.assertIsNone(await ws_auth.authenticate_websocket(websocket, "messenger"))
        self.assertEqual(websocket.close.await_args.kwargs["code"], 1013)

    async def test_realtime_ready_frame_has_a_send_deadline(self):
        websocket = _socket()

        async def stalled_send(*args, **kwargs):
            await asyncio.sleep(10)

        websocket.send_json.side_effect = stalled_send
        session = AsyncMock()
        with (
            patch.object(ws_auth.realtime_service, "consume_ticket", new_callable=AsyncMock,
                         return_value={"account_uid": str(uuid4())}),
            patch.object(ws_auth.Database, "get_session", new_callable=AsyncMock, return_value=session),
            patch.object(ws_auth, "active_account_access_restriction",
                         new_callable=AsyncMock, return_value=None),
            patch.object(ws_auth.config, "REALTIME_SEND_TIMEOUT_SECONDS", 0.01),
        ):
            self.assertIsNone(await ws_auth.authenticate_websocket(websocket, "messenger"))
        self.assertEqual(websocket.close.await_args.kwargs["code"], 1013)
        session.close.assert_awaited_once()
