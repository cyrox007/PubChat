import asyncio
import os
import unittest

from sqlalchemy import delete, select

from components.model_registry import ensure_models_registered
from components.identity.model import PlatformPermission, PlatformRole, RolePermission
from components.moderation.lexicon_model import (
    ModerationLexiconState, ModerationLexiconRevision, ModerationLexiconAudit,
)
from components.moderation.lexicon_schemas import (
    LexiconActivate, LexiconRevisionCreate, LexiconRuleInput,
)
from components.moderation.lexicon_service import (
    activate_revision, create_revision, list_policy, get_revision,
    simulate_policy, policy_audit,
)
from database import Database


@unittest.skipUnless(
    os.getenv("PUBCHAT_POSTGRES_INTEGRATION") == "1",
    "Needs migrated disposable PostgreSQL integration database",
)
class ModerationLexiconPostgresIntegration(unittest.TestCase):
    def test_draft_serialization_shadow_rollback_and_admin_permission(self):
        async def run():
            ensure_models_registered()
            async with Database.sessionmaker()() as db:
                state = await db.get(ModerationLexiconState, 1)
                self.assertIsNotNone(state)
                self.assertEqual(state.mode, "off")
                self.assertEqual(state.active_revision, 0)
                permission_id = (await db.execute(
                    select(PlatformPermission.id).where(PlatformPermission.name == "moderation.policy.manage")
                )).scalar_one()
                role_names = (await db.execute(
                    select(PlatformRole.name).join(RolePermission, RolePermission.role_id == PlatformRole.id)
                    .where(RolePermission.permission_id == permission_id)
                )).scalars().all()
                self.assertEqual(role_names, ["admin"])

            async def save_one(term):
                async with Database.sessionmaker()() as db:
                    return await create_revision(
                        db, None, LexiconRevisionCreate(
                            rules=[LexiconRuleInput(term=term, match_mode="token")],
                            reason="Интеграционная проверка черновика",
                        ),
                    )

            try:
                first, second = await asyncio.gather(
                    save_one("пример"), save_one("фраза")
                )
                self.assertNotEqual(first["revision"], second["revision"])
                self.assertEqual(abs(first["revision"] - second["revision"]), 1)
                async with Database.sessionmaker()() as db:
                    value = await list_policy(db)
                    self.assertEqual(value["active_revision"], 0)
                    self.assertEqual(value["active_rules"], [])
                    self.assertFalse(value["enforced"])
                    result = await simulate_policy(db, "пример", first["revision"])
                    self.assertEqual(len(result["matches"]), 1)
                    self.assertFalse(result["enforced"])
                    self.assertEqual(result["preview"], "••••••")
                    selected = await get_revision(db, first["revision"])
                    self.assertEqual(selected["rules"][0]["term"], "пример")

                async with Database.sessionmaker()() as db:
                    state = await activate_revision(
                        db, None, LexiconActivate(
                            revision=second["revision"], mode="shadow",
                            reason="Проверка публикации shadow",
                        ),
                    )
                    self.assertEqual(state["mode"], "shadow")
                async with Database.sessionmaker()() as db:
                    value = await list_policy(db)
                    self.assertEqual(value["active_revision"], second["revision"])
                    self.assertEqual(value["active_rules"][0]["term"], "фраза")
                    events = await policy_audit(db)
                    self.assertIn("activated", {e["action"] for e in events})
                async with Database.sessionmaker()() as db:
                    state = await activate_revision(
                        db, None, LexiconActivate(
                            revision=first["revision"], mode="shadow",
                            reason="Откат на предыдущую ревизию",
                        ),
                    )
                    self.assertEqual(state["revision"], first["revision"])
                    original = await get_revision(db, second["revision"])
                    self.assertEqual(original["rules"][0]["term"], "фраза")
                async with Database.sessionmaker()() as db:
                    await activate_revision(
                        db, None, LexiconActivate(
                            revision=0, mode="off", reason="Окончание интеграционного теста",
                        ),
                    )
            finally:
                async with Database.sessionmaker()() as cleanup:
                    state = await cleanup.get(ModerationLexiconState, 1, with_for_update=True)
                    state.active_revision = 0
                    state.mode = "off"
                    state.updated_by_account_uid = None
                    await cleanup.execute(delete(ModerationLexiconAudit))
                    await cleanup.execute(delete(ModerationLexiconRevision))
                    await cleanup.commit()

        asyncio.run(run())
