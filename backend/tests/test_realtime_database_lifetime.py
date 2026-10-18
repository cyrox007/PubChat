import asyncio
import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import WebSocketDisconnect
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from components.decorators.db import get_realtime_session, release_realtime_session
from settings import config
from views.rooms.ws_handlers import process_incoming_messages
from views.messenger.ws_handlers import handle_private_messages
from views.calls.ws_handlers import handle_call_connection


class RealtimeDatabaseLifetimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_room_and_messenger_release_before_waiting_for_frames(self):
        for handler, args in [
            (process_incoming_messages, (uuid4(), uuid4())),
            (handle_private_messages, (uuid4(),)),
        ]:
            session = AsyncMock()
            websocket = MagicMock()

            async def receive():
                session.commit.assert_awaited_once()
                session.close.assert_awaited_once()
                raise WebSocketDisconnect()

            websocket.receive_json = receive
            with self.assertRaises(WebSocketDisconnect):
                await handler(websocket, *args, session)

    async def test_calls_do_not_checkout_a_connection_on_entry_or_while_idle(self):
        session = AsyncMock()
        websocket = MagicMock()

        async def receive():
            session.commit.assert_awaited_once()
            session.close.assert_awaited_once()
            raise WebSocketDisconnect()

        websocket.receive_json = receive
        with patch("components.decorators.db.Database.sessionmaker", return_value=lambda: session), \
             patch("components.decorators.db.Database.get_session", new_callable=AsyncMock) as eager, \
             patch("views.calls.ws_handlers.call_manager.connect_to_messenger", new_callable=AsyncMock), \
             patch("views.calls.ws_handlers.call_manager.disconnect", new_callable=AsyncMock):
            await handle_call_connection(websocket, {"user_uid": str(uuid4())})
            eager.assert_not_awaited()

    async def test_frame_failure_rolls_back_and_closes_lazy_session(self):
        session = AsyncMock()

        @get_realtime_session
        async def fail(db_session=None):
            raise ValueError("frame failure")

        with patch("components.decorators.db.Database.sessionmaker", return_value=lambda: session):
            with self.assertRaises(Exception):
                await fail()
        session.rollback.assert_awaited_once()
        session.close.assert_awaited_once()


@unittest.skipUnless(os.getenv("PUBCHAT_POSTGRES_INTEGRATION") == "1", "Requires PostgreSQL")
class RealtimeDatabasePoolIntegrationTests(unittest.TestCase):
    def test_single_connection_pool_is_available_between_frames(self):
        async def check():
            engine = create_async_engine(config.database_url(async_mode=True), pool_size=1, max_overflow=0, pool_timeout=1)
            maker = async_sessionmaker(engine, expire_on_commit=False)
            session = maker()
            try:
                for _ in range(3):
                    await session.execute(text("SELECT 1"))
                    self.assertEqual(engine.pool.checkedout(), 1)
                    await release_realtime_session(session)
                    self.assertEqual(engine.pool.checkedout(), 0)
                    # Another request can use the only connection while this socket is idle.
                    async with maker() as other:
                        self.assertEqual((await other.execute(text("SELECT 1"))).scalar_one(), 1)
            finally:
                await session.close()
                await engine.dispose()
        asyncio.run(check())
