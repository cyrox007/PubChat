"""Real PostgreSQL regression for an async reply to a different room member."""
import asyncio
import os
import unittest
from uuid import uuid4

from sqlalchemy import delete

from components.message.model import Message
from components.model_registry import ensure_models_registered
from components.room.model import Room
from components.user.model import User
from database import Database


@unittest.skipUnless(
    os.getenv("PUBCHAT_POSTGRES_INTEGRATION") == "1",
    "PostgreSQL integration environment is not enabled",
)
class SpaceReplyPostgresIntegrationTests(unittest.TestCase):
    def test_quoted_peer_author_is_loaded_without_async_lazy_io(self):
        async def scenario():
            ensure_models_registered()
            writer_uid, peer_uid, room_uid = uuid4(), uuid4(), uuid4()
            writer_name = f"reply-writer-{writer_uid.hex[:10]}"
            peer_name = f"reply-peer-{peer_uid.hex[:10]}"
            async with Database.sessionmaker()() as db:
                db.add_all([
                    User(uid=writer_uid, username=writer_name),
                    User(uid=peer_uid, username=peer_name),
                ])
                await db.flush()
                db.add(Room(uid=room_uid, name="Reply author SQL regression",
                            owner_uid=peer_uid, is_active=True))
                await db.commit()

            try:
                # Two fresh sessions deliberately do not preload the quoted
                # peer's ORM User into the reply author's identity map.
                async with Database.sessionmaker()() as db:
                    source = await Message.create_message(db, {
                        "room_uid": str(room_uid), "sender_uid": str(peer_uid),
                        "content": "Quoted from a different user", "content_type": "text",
                    })
                async with Database.sessionmaker()() as db:
                    response = await Message.create_message(db, {
                        "room_uid": str(room_uid), "sender_uid": str(writer_uid),
                        "content": "Reply should survive", "content_type": "text",
                        "reply_to_uid": source["uid"],
                    })
                    self.assertEqual(response["reply_to"]["uid"], source["uid"])
                    self.assertEqual(response["reply_to"]["sender"]["name"], peer_name)
                    self.assertEqual(response["sender"]["username"], writer_name)
                async with Database.sessionmaker()() as db:
                    recent = await Message.get_last_messages(db, room_uid, limit=5)
                    self.assertTrue(any(
                        item["uid"] == response["uid"] and
                        item["reply_to"]["sender"]["name"] == peer_name
                        for item in recent
                    ))
            finally:
                async with Database.sessionmaker()() as db:
                    await db.execute(delete(Message).where(Message.room_uid == room_uid))
                    await db.execute(delete(Room).where(Room.uid == room_uid))
                    await db.execute(delete(User).where(User.uid.in_([writer_uid, peer_uid])))
                    await db.commit()

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
