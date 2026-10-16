import json
import unittest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect

from app import app
from components.realtime.schemas import RealtimeAuthFrame, RealtimeTicketRequest
from components.realtime.service import RealtimeService
from settings import config
from views.realtime.ws_auth import authenticate_websocket


class RealtimeContractTests(unittest.TestCase):
    def test_v2_routes_have_no_credentials_in_url(self):
        paths = {route.path for route in app.routes}
        self.assertIn('/realtime/v2/tickets', paths)
        self.assertIn('/ws/v2/rooms/{room_uid}', paths)
        self.assertIn('/ws/v2/messenger', paths)
        credential_segment = '{' + 'token' + '}'
        self.assertFalse(any(credential_segment in path for path in paths))

    def test_room_ticket_requires_room_uid(self):
        with self.assertRaises(ValidationError):
            RealtimeTicketRequest(target='room')

    def test_messenger_ticket_rejects_room_uid(self):
        with self.assertRaises(ValidationError):
            RealtimeTicketRequest(target='messenger', room_uid=uuid4())

    def test_auth_frame_rejects_short_ticket(self):
        with self.assertRaises(ValidationError):
            RealtimeAuthFrame(type='auth', ticket='short')


class FakePipeline:
    def __init__(self):
        self.expire_calls = []

    def set(self, *args, **kwargs):
        return self

    def zadd(self, *args, **kwargs):
        return self

    def expire(self, key, ttl):
        self.expire_calls.append((key, ttl))
        return self

    async def execute(self):
        return []


class FakeRedis:
    def __init__(self, record):
        self.record = record
        self.last_pipeline = None

    async def get(self, key):
        return json.dumps(self.record)

    def pipeline(self, transaction=False):
        self.last_pipeline = FakePipeline()
        return self.last_pipeline


class RealtimeLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.previous_debug = config.DEBUG
        config.DEBUG = True
        self.service = RealtimeService()

    async def asyncTearDown(self):
        config.DEBUG = self.previous_debug

    async def test_debug_ticket_is_one_time_and_scoped(self):
        account_uid = uuid4()
        room_uid = uuid4()
        ticket, ttl = await self.service.issue_ticket(account_uid, 'room', room_uid)
        self.assertGreaterEqual(ttl, 1)

        payload = await self.service.consume_ticket(ticket, 'room', room_uid)
        self.assertIsNotNone(payload)
        self.assertEqual(payload['account_uid'], str(account_uid))
        self.assertIsNone(await self.service.consume_ticket(ticket, 'room', room_uid))

    async def test_ticket_scope_mismatch_consumes_ticket(self):
        ticket, _ = await self.service.issue_ticket(uuid4(), 'messenger')
        self.assertIsNone(await self.service.consume_ticket(ticket, 'room', uuid4()))
        self.assertIsNone(await self.service.consume_ticket(ticket, 'messenger'))

    async def test_client_event_id_is_idempotent_per_scope(self):
        account_uid = uuid4()
        event_id = str(uuid4())

        self.assertTrue(await self.service.claim_event(account_uid, 'space:one', event_id))
        self.assertFalse(await self.service.claim_event(account_uid, 'space:one', event_id))
        self.assertTrue(await self.service.claim_event(account_uid, 'space:two', event_id))

    async def test_failed_event_claim_can_be_released_for_retry(self):
        account_uid = uuid4()
        event_id = str(uuid4())
        scope = 'direct-message:target'

        self.assertTrue(await self.service.claim_event(account_uid, scope, event_id))
        await self.service.release_event(account_uid, scope, event_id)
        self.assertTrue(await self.service.claim_event(account_uid, scope, event_id))

    async def test_peer_disconnect_during_auth_does_not_send_second_close(self):
        websocket = MagicMock()
        websocket.accept = AsyncMock()
        websocket.receive_json = AsyncMock(side_effect=WebSocketDisconnect(code=1006))
        websocket.close = AsyncMock()

        result = await authenticate_websocket(websocket, target='messenger')

        self.assertIsNone(result)
        websocket.accept.assert_awaited_once()
        websocket.close.assert_not_awaited()

    async def test_heartbeat_refreshes_user_and_room_presence_index_ttls(self):
        account_uid = uuid4()
        room_uid = uuid4()
        connection_id = 'connection-1'
        fake_redis = FakeRedis(
            {
                'connection_id': connection_id,
                'user_uid': str(account_uid),
                'target': 'room',
                'room_uid': str(room_uid),
                'expires_at': 0,
            }
        )
        self.service._redis = fake_redis

        await self.service.touch_connection(connection_id)

        ttl = config.REALTIME_PRESENCE_TTL_SECONDS * 2
        self.assertIn(
            (self.service._presence_user_key(account_uid), ttl),
            fake_redis.last_pipeline.expire_calls,
        )
        self.assertIn(
            (self.service._presence_room_key(room_uid), ttl),
            fake_redis.last_pipeline.expire_calls,
        )

    async def test_room_presence_deduplicates_multiple_connections_per_account(self):
        room_uid = uuid4()
        first_account = uuid4()
        second_account = uuid4()

        await self.service.register_connection('first-tab', first_account, 'room', room_uid)
        await self.service.register_connection('second-tab', first_account, 'room', room_uid)
        await self.service.register_connection('other-person', second_account, 'room', room_uid)

        self.assertEqual(
            await self.service.room_users(room_uid),
            sorted([str(first_account), str(second_account)]),
        )

        await self.service.unregister_connection('first-tab')
        self.assertIn(str(first_account), await self.service.room_users(room_uid))

        await self.service.unregister_connection('second-tab')
        self.assertNotIn(str(first_account), await self.service.room_users(room_uid))


if __name__ == '__main__':
    unittest.main()
