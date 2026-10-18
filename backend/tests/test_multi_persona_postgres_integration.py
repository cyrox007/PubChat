import asyncio
import os
import unittest
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import delete

from components.identity.model import Account, IdentitySession, Persona, PrivacySettings
from components.identity.schemas import PersonaCreateRequest
from components.identity.service import (
    activate_account_persona, create_account_persona,
    list_account_personas, selected_persona,
)
from components.model_registry import ensure_models_registered
from database import Database


@unittest.skipUnless(
    os.getenv("PUBCHAT_POSTGRES_INTEGRATION") == "1",
    "PostgreSQL integration environment is not enabled",
)
class MultiPersonaPostgresIntegrationTests(unittest.TestCase):
    def test_session_scoping_and_cross_account_denial(self):
        async def scenario():
            ensure_models_registered()
            owner, stranger, primary_uid = uuid4(), uuid4(), uuid4()
            session_a, session_b = uuid4(), uuid4()

            async with Database.sessionmaker()() as db:
                db.add_all([
                    Account(uid=owner, status="active", trust_level="new"),
                    Account(uid=stranger, status="active", trust_level="new"),
                ])
                await db.flush()
                db.add(Persona(
                    uid=primary_uid, account_uid=owner, handle=f"root_{owner.hex[:15]}",
                    display_name="Main", is_primary=True,
                ))
                db.add_all([
                    IdentitySession(
                        uid=uid, account_uid=owner,
                        refresh_token_hash=f"test-{uuid4().hex}",
                        expires_at=datetime.utcnow() + timedelta(days=2),
                    )
                    for uid in (session_a, session_b)
                ])
                await db.commit()

            try:
                async with Database.sessionmaker()() as db:
                    owner_account = await db.get(Account, owner)
                    alt = await create_account_persona(
                        db, owner_account, PersonaCreateRequest(
                            handle=f"alt_{owner.hex[:15]}", display_name="Other"
                        ),
                    )
                    alt_uid = alt.uid
                    privacy = await db.get(PrivacySettings, alt_uid)
                    self.assertEqual(privacy.profile_visibility, "private")
                    self.assertEqual(privacy.dm_policy, "nobody")

                async with Database.sessionmaker()() as db:
                    with self.assertRaises(HTTPException) as denied:
                        await activate_account_persona(db, stranger, str(session_a), alt_uid)
                    self.assertIn(denied.exception.status_code, (401, 404))
                    await db.rollback()

                async with Database.sessionmaker()() as db:
                    await activate_account_persona(db, owner, str(session_a), alt_uid)
                    first = await selected_persona(db, owner, str(session_a))
                    second = await selected_persona(db, owner, str(session_b))
                    self.assertEqual(first.uid, alt_uid)
                    self.assertEqual(second.uid, primary_uid)
                    listing = await list_account_personas(db, owner, str(session_a))
                    self.assertEqual(len(listing["personas"]), 2)
                    self.assertEqual(listing["active_persona_uid"], str(alt_uid))
            finally:
                async with Database.sessionmaker()() as db:
                    for uid in (owner, stranger):
                        await db.execute(delete(Account).where(Account.uid == uid))
                    await db.commit()

        asyncio.run(scenario())


if __name__ == "__main__":
    unittest.main()
