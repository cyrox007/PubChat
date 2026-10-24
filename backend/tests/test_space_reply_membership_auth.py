"""Identity v2 Space membership must authorize HTTP replies to other members."""
import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException

from components.message.actions import active_room_member, ensure_message_access
from components.room.model import RoomBan


def result(row):
    cursor = MagicMock()
    cursor.scalar_one_or_none.return_value = row
    return cursor


class SpaceReplyMembershipTests(unittest.TestCase):
    def test_active_modern_membership_allows_peer_reply_without_legacy_row(self):
        async def scenario():
            account_uid, user_uid, room_uid = uuid4(), uuid4(), uuid4()
            account = SimpleNamespace(uid=account_uid, status="active", deleted_at=None)
            db = MagicMock()
            db.execute = AsyncMock(side_effect=[result(account), result(uuid4())])
            with patch.object(RoomBan, "is_user_banned", new_callable=AsyncMock, return_value=False):
                self.assertTrue(await active_room_member(db, room_uid, user_uid))
                await ensure_message_access(
                    # A second explicit check uses the same active Account/Space
                    # contract, not an obsolete RoomMember requirement.
                    _db_for_membership(account, room_uid), "room",
                    SimpleNamespace(author_uid=uuid4(), room_uid=room_uid), user_uid,
                )
            self.assertEqual(db.execute.await_count, 2)
            member_query = str(db.execute.await_args.args[0]).lower()
            self.assertIn("space_memberships", member_query)
            self.assertIn("status", member_query)
        asyncio.run(scenario())

    def test_removed_modern_member_cannot_use_stale_legacy_row(self):
        async def scenario():
            account = SimpleNamespace(uid=uuid4(), status="active", deleted_at=None)
            db = MagicMock()
            db.execute = AsyncMock(side_effect=[result(account), result(None)])
            with patch.object(RoomBan, "is_user_banned", new_callable=AsyncMock, return_value=False):
                self.assertFalse(await active_room_member(db, uuid4(), uuid4()))
            self.assertEqual(db.execute.await_count, 2)
        asyncio.run(scenario())

    def test_suspended_account_is_not_authorized(self):
        async def scenario():
            db = MagicMock()
            db.execute = AsyncMock(return_value=result(
                SimpleNamespace(uid=uuid4(), status="suspended", deleted_at=None)
            ))
            with patch.object(RoomBan, "is_user_banned", new_callable=AsyncMock, return_value=False):
                self.assertFalse(await active_room_member(db, uuid4(), uuid4()))
            db.execute.assert_awaited_once()
        asyncio.run(scenario())

    def test_real_space_ban_overrides_modern_membership(self):
        async def scenario():
            db = MagicMock()
            db.execute = AsyncMock()
            with patch.object(RoomBan, "is_user_banned", new_callable=AsyncMock, return_value=True):
                self.assertFalse(await active_room_member(db, uuid4(), uuid4()))
            db.execute.assert_not_awaited()
        asyncio.run(scenario())

    def test_only_unmigrated_legacy_member_uses_legacy_table(self):
        async def scenario():
            db = MagicMock()
            db.execute = AsyncMock(side_effect=[result(None), result(99)])
            with patch.object(RoomBan, "is_user_banned", new_callable=AsyncMock, return_value=False):
                self.assertTrue(await active_room_member(db, uuid4(), uuid4()))
            self.assertIn("room_members", str(db.execute.await_args.args[0]))
        asyncio.run(scenario())

    def test_nonmember_cannot_read_someone_elses_room_message(self):
        async def scenario():
            db = MagicMock()
            db.execute = AsyncMock(side_effect=[result(None), result(None)])
            with patch.object(RoomBan, "is_user_banned", new_callable=AsyncMock, return_value=False):
                with self.assertRaises(HTTPException) as raised:
                    await ensure_message_access(
                        db, "room", SimpleNamespace(author_uid=uuid4(), room_uid=uuid4()),
                        uuid4(),
                    )
            self.assertEqual(raised.exception.status_code, 403)
        asyncio.run(scenario())


def _db_for_membership(account, room_uid):
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[result(account), result(uuid4())])
    return db


if __name__ == "__main__":
    unittest.main()
