import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from components.notification.space_reply_delivery import eligible_space_reply


class SpaceReplyRoomLookupTests(unittest.IsolatedAsyncioTestCase):
    async def test_reply_eligibility_looks_up_public_uuid_instead_of_integer_primary_key(self):
        room_uid, sender, recipient = uuid4(), uuid4(), uuid4()
        room_result, member_result, blocked_result = MagicMock(), MagicMock(), MagicMock()
        room_result.scalars.return_value.first.return_value = SimpleNamespace(is_active=True)
        member_result.scalar_one_or_none.return_value = uuid4()
        blocked_result.scalar_one_or_none.return_value = None
        db = SimpleNamespace(
            execute=AsyncMock(side_effect=[room_result, member_result, blocked_result]),
            get=AsyncMock(side_effect=AssertionError('UUID must not be passed to integer primary-key lookup')),
        )
        self.assertTrue(await eligible_space_reply(db, room_uid, sender, recipient))
        query = db.execute.await_args_list[0].args[0]
        self.assertIn('rooms.uid =', str(query))
        self.assertNotIn('rooms.id =', str(query))
        self.assertIn(room_uid, query.compile().params.values())
        db.get.assert_not_awaited()
