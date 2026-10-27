"""Real PostgreSQL acceptance: client frontId maps to one canonical uid."""
import asyncio
import os
import unittest
from uuid import uuid4

from sqlalchemy import delete, func, select

from components.message.model import Message, PrivateMessage
from components.model_registry import ensure_models_registered
from components.room.model import Room
from components.user.model import User
from database import Database


@unittest.skipUnless(
    os.getenv("PUBCHAT_POSTGRES_INTEGRATION") == "1",
    "PostgreSQL integration environment is not enabled",
)
class MessageFrontIdPostgresIntegrationTests(unittest.TestCase):
    def test_space_and_dm_replay_and_scope(self):
        async def scenario():
            ensure_models_registered()
            writer, recipient, room_uid = uuid4(), uuid4(), uuid4()
            client_id = str(uuid4())
            async with Database.sessionmaker()() as db:
                db.add_all([
                    User(uid=writer, username=f"front-w-{writer.hex[:8]}"),
                    User(uid=recipient, username=f"front-r-{recipient.hex[:8]}"),
                ])
                await db.flush()
                db.add(Room(uid=room_uid, name="FrontId retry integration",
                            owner_uid=writer, is_active=True))
                await db.commit()
            try:
                room_payload = {
                    "sender_uid": str(writer), "room_uid": str(room_uid),
                    "content": "first", "frontId": client_id,
                }
                async with Database.sessionmaker()() as db:
                    saved = await Message.create_message(db, room_payload)
                    self.assertEqual(saved["frontId"], client_id)
                async with Database.sessionmaker()() as db:
                    duplicate = await Message.create_message(db, {**room_payload, "content": "changed on retry"})
                    self.assertTrue(duplicate.pop("_replayed"))
                    self.assertEqual(saved["uid"], duplicate["uid"])
                    self.assertEqual(duplicate["content"], "first")
                async with Database.sessionmaker()() as db:
                    other_author = await Message.create_message(db, {
                        **room_payload, "sender_uid": str(recipient), "content": "legitimate peer",
                    })
                    self.assertNotEqual(other_author["uid"], saved["uid"])
                dm_payload = {
                    "sender_uid": str(writer), "receiver_uid": str(recipient),
                    "content": "DM original", "content_type": "text", "frontId": client_id,
                }
                async with Database.sessionmaker()() as db:
                    first = await PrivateMessage.create_private_message(db, dm_payload)
                async with Database.sessionmaker()() as db:
                    replay = await PrivateMessage.create_private_message(db, {**dm_payload, "content": "bad retry"})
                    self.assertTrue(replay.pop("_replayed"))
                    self.assertEqual(first["uid"], replay["uid"])
                    self.assertEqual(replay["content"], "DM original")
                async with Database.sessionmaker()() as db:
                    count = (await db.execute(select(func.count(Message.uid)).where(
                        Message.room_uid == room_uid, Message.author_uid == writer,
                        Message.front_id == client_id,
                    ))).scalar_one()
                    self.assertEqual(count, 1)
            finally:
                async with Database.sessionmaker()() as db:
                    await db.execute(delete(PrivateMessage).where(
                        PrivateMessage.sender_uid == writer, PrivateMessage.receiver_uid == recipient,
                        PrivateMessage.front_id == client_id,
                    ))
                    await db.execute(delete(Message).where(Message.room_uid == room_uid))
                    await db.execute(delete(Room).where(Room.uid == room_uid))
                    await db.execute(delete(User).where(User.uid.in_([writer, recipient])))
                    await db.commit()
        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
