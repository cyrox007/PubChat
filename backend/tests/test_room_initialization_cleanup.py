import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from starlette.websockets import WebSocketState
from views.rooms import ws_handlers

class RoomInitializationCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_closed_socket_is_cleaned_even_when_initialization_did_not_finish(self):
        socket=SimpleNamespace(application_state=WebSocketState.DISCONNECTED)
        room=uuid4()
        with patch.object(ws_handlers, 'initialize_websocket', new_callable=AsyncMock, side_effect=RuntimeError('Cannot call send after close')), patch.object(ws_handlers.manager, 'disconnect', new_callable=AsyncMock) as cleanup, patch.object(ws_handlers.logger, 'exception') as error:
            await ws_handlers.handle_websocket_connection.__wrapped__(socket, room, {'user_uid':str(uuid4())}, db_session=AsyncMock())
            cleanup.assert_awaited_once_with(socket, room)
            error.assert_not_called()
