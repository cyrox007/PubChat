import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from starlette.websockets import WebSocketDisconnect
from views.realtime import ws_auth

class RealtimeAuthDisconnectTests(unittest.IsolatedAsyncioTestCase):
    async def test_disconnect_while_sending_ready_is_not_an_asgi_failure(self):
        websocket=SimpleNamespace(accept=AsyncMock(), receive_json=AsyncMock(return_value={'type':'auth','ticket':'t'*32}), send_json=AsyncMock(side_effect=WebSocketDisconnect(1006)), state=SimpleNamespace())
        session=AsyncMock()
        with patch.object(ws_auth.realtime_service,'consume_ticket',new_callable=AsyncMock,return_value={'account_uid':str(uuid4())}), patch.object(ws_auth.Database,'get_session',new_callable=AsyncMock,return_value=session), patch.object(ws_auth,'active_account_access_restriction',new_callable=AsyncMock,return_value=None):
            self.assertIsNone(await ws_auth.authenticate_websocket(websocket,'room',uuid4()))
            session.close.assert_awaited_once()
