import unittest
from uuid import uuid4

from app import app
from components.moderation.lexicon_matcher import simulate_rules
from components.moderation.lexicon_model import (
    ModerationLexiconAudit, ModerationLexiconRevision, ModerationLexiconState,
)
from components.moderation.lexicon_schemas import (
    LexiconActivate, LexiconRevisionCreate, LexiconRuleInput, LexiconSimulate,
)
from pydantic import ValidationError
from views.moderation.lexicon_routers import require_lexicon_editor
from components.auth.permissions import require_platform_permission


def rule(term="плох", match_mode="stem", variants=None, exceptions=None, **extra):
    return LexiconRuleInput(
        uid=uuid4(), term=term, match_mode=match_mode, language="ru",
        variants=variants or [], exceptions=exceptions or [],
        action="mask", **extra
    ).model_dump(mode="json")


class LexiconContractTests(unittest.TestCase):
    def test_admin_only_routes_exist_and_require_explicit_permission(self):
        expected = {
            "/trust-safety/v1/lexicon",
            "/trust-safety/v1/lexicon/revisions",
            "/trust-safety/v1/lexicon/revisions/{revision}",
            "/trust-safety/v1/lexicon/activate",
            "/trust-safety/v1/lexicon/simulate",
            "/trust-safety/v1/lexicon/audit",
        }
        routes = [route for route in app.routes if route.path in expected]
        self.assertEqual({r.path for r in routes}, expected)
        for route in routes:
            self.assertTrue(
                any(dep.call is require_lexicon_editor for dep in route.dependant.dependencies),
                route.path,
            )
        self.assertIn("moderation.policy.manage", require_lexicon_editor.__code__.co_consts)
        self.assertIsNotNone(require_platform_permission)

    def test_revision_tables_keep_policy_distinct_from_user_text(self):
        self.assertEqual(ModerationLexiconState.__tablename__, "moderation_lexicon_state")
        self.assertIn("rules", ModerationLexiconRevision.__table__.c)
        self.assertIn("actor_account_uid", ModerationLexiconAudit.__table__.c)
        for table in (ModerationLexiconState.__table__, ModerationLexiconRevision.__table__, ModerationLexiconAudit.__table__):
            for unsafe in ("message", "text", "raw_prompt", "history", "matched_text"):
                self.assertNotIn(unsafe, table.c)

    def test_stem_inflections_and_exact_boundaries(self):
        v = simulate_rules("Это плохая фраза. А плохим словом не пользуемся.", [rule()], revision=9, mode="shadow")
        self.assertEqual(len(v["matches"]), 2)
        self.assertNotIn("плохая", v["preview"])
        self.assertFalse(v["enforced"])
        exact = simulate_rules("скотина котика кот", [rule("кот", "token")], revision=0, mode="off")
        self.assertEqual(len(exact["matches"]), 1)
        self.assertEqual(exact["preview"], "скотина котика •••")

    def test_mixed_alphabet_and_split_punctuation(self):
        result = simulate_rules("cпaм и с*п*а*м", [rule("спам", "token")], revision=1, mode="shadow")
        self.assertEqual(len(result["matches"]), 2)
        self.assertNotIn("cпaм", result["preview"])
        self.assertNotIn("с*п*а*м", result["preview"])

    def test_phrase_and_variations(self):
        a = rule("очень грубо", "phrase", variants=["совсем грубо"])
        v = simulate_rules("Очень грубо. Совсем грубо.", [a], revision=2, mode="shadow")
        self.assertEqual(len(v["matches"]), 2)
        self.assertEqual(v["matches"][0]["match_kind"], "phrase")

    def test_exception_and_disabled_rules_avoid_false_positives(self):
        a = rule("кот", "token", exceptions=["кот"])
        b = rule("добр", "stem")
        b["enabled"] = False
        value = simulate_rules("кот добрый", [a, b], revision=1, mode="shadow")
        self.assertEqual(value["matches"], [])
        self.assertEqual(value["preview"], "кот добрый")

    def test_rules_have_configurable_surfaces_and_severity(self):
        entry = rule("спам", "token")
        entry["surfaces"] = ["space_chat", "comment"]
        entry["severity"] = "high"
        in_chat = simulate_rules("спам", [entry], revision=1, mode="shadow", surface="space_chat")
        in_dm = simulate_rules("спам", [entry], revision=1, mode="shadow", surface="messenger_plaintext")
        self.assertEqual(len(in_chat["matches"]), 1)
        self.assertEqual(in_chat["matches"][0]["severity"], "high")
        self.assertEqual(in_dm["matches"], [])
        self.assertEqual(in_dm["preview"], "спам")
        with self.assertRaises(ValidationError):
            LexiconRuleInput(term="спам", surfaces=["all", "space_chat"])
        with self.assertRaises(ValidationError):
            LexiconRuleInput(term="спам", surfaces=["space_chat", "space_chat"])
        with self.assertRaises(ValidationError):
            LexiconSimulate(text="спам", surface="unknown")

    def test_common_latin_leetspeak(self):
        term = LexiconRuleInput(term="spam", language="en", match_mode="token", action="mask").model_dump(mode="json")
        value = simulate_rules("sp4m", [term], revision=1, mode="off")
        self.assertEqual(len(value["matches"]), 1)
        self.assertEqual(value["preview"], "••••")

    def test_actions_are_only_preview_no_automatic_sanction(self):
        a = rule("bad", "token")
        a["language"] = "en"
        a["action"] = "reject"
        result = simulate_rules("bad", [a], revision=1, mode="shadow")
        self.assertTrue(result["would_block"])
        self.assertFalse(result["enforced"])
        self.assertEqual(result["matches"][0]["action"], "reject")

    def test_unknown_rule_actions_regex_and_enforcement_are_rejected(self):
        for invalid in (
            dict(term="пример", match_mode="regex"),
            dict(term="пример", action="permanent_ban"),
            dict(term="а", match_mode="stem"),
            dict(term="сначала потом", match_mode="token"),
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                LexiconRuleInput(**invalid)
        for mode in ("enforce", "allow_everything", "autoban"):
            with self.assertRaises(ValidationError):
                LexiconActivate(revision=1, mode=mode, reason="Проверка политики")
        with self.assertRaises(ValidationError):
            LexiconActivate(revision=0, mode="shadow", reason="Проверка политики")

    def test_server_bounds_policy_and_preview(self):
        with self.assertRaises(ValidationError):
            LexiconRevisionCreate(rules=[LexiconRuleInput(term="слово")] * 201, reason="Достаточное основание")
        with self.assertRaises(ValidationError):
            LexiconRuleInput(term="а" * 121)
        with self.assertRaises(ValidationError):
            LexiconRuleInput(term="правило", variants=["версия"] * 21)
        with self.assertRaises(ValidationError):
            LexiconRevisionCreate(rules=[], reason=" ")
        with self.assertRaises(ValidationError):
            LexiconSimulate(text="a" * 4001)

    def test_active_revisions_are_explicit_and_audited(self):
        self.assertEqual(LexiconActivate(revision=1, mode="shadow", reason="В тестовом режиме").mode, "shadow")
        self.assertEqual(LexiconRevisionCreate(
            rules=[LexiconRuleInput(term="пример")], reason="Новая версия словаря"
        ).rules[0].action, "mask")



class ModerationPreflightShadowTests(unittest.IsolatedAsyncioTestCase):
    async def test_shadow_preflight_observes_without_changing_content(self):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, patch
        from components.moderation.lexicon_service import inspect_plaintext_write
        import components.moderation.lexicon_service as service

        policy_state = SimpleNamespace(mode="shadow", active_revision=7)
        revision = SimpleNamespace(rules=[rule("спам", "token")])
        db = SimpleNamespace(get=AsyncMock(return_value=revision))
        with patch.object(service, "_state", AsyncMock(return_value=policy_state)):
            with self.assertLogs(service.__name__, level="INFO") as logs:
                await inspect_plaintext_write(db, "спам", surface="space_chat", operation="reply")
        self.assertTrue(any("moderation_shadow_match" in line for line in logs.output))
        self.assertTrue(all("спам" not in line for line in logs.output))
        db.get.assert_awaited_once()

    async def test_shadow_initial_send_supports_both_plaintext_surfaces(self):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, patch
        import components.moderation.lexicon_service as service

        active = SimpleNamespace(mode="shadow", active_revision=3)
        revision = SimpleNamespace(rules=[rule("спам", "token")])
        db = SimpleNamespace(get=AsyncMock(return_value=revision))
        with patch.object(service, "_state", AsyncMock(return_value=active)):
            with self.assertLogs(service.__name__, level="INFO") as logs:
                await service.inspect_plaintext_write(
                    db, "спам", surface="space_chat", operation="send"
                )
                await service.inspect_plaintext_write(
                    db, "спам", surface="messenger_plaintext", operation="send"
                )
        self.assertEqual(len(logs.output), 2)
        self.assertTrue(all("operation=send" in entry for entry in logs.output))
        self.assertTrue(all("спам" not in entry for entry in logs.output))

    async def test_media_caption_shadow_respects_surface_scope(self):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, patch
        import components.moderation.lexicon_service as service

        scoped = rule("спам", "token")
        scoped["surfaces"] = ["media_caption"]
        state = SimpleNamespace(mode="shadow", active_revision=5)
        revision = SimpleNamespace(rules=[scoped])
        db = SimpleNamespace(get=AsyncMock(return_value=revision))
        with patch.object(service, "_state", AsyncMock(return_value=state)):
            with self.assertLogs(service.__name__, level="INFO") as captured:
                await service.inspect_plaintext_write(
                    db, "спам", surface="media_caption", operation="send"
                )
            self.assertEqual(len(captured.output), 1)
            self.assertIn("surface=media_caption", captured.output[0])
            self.assertNotIn("спам", captured.output[0])
            self.assertNotIn("спам", str(db.get.call_args))

    async def test_off_policy_never_loads_dictionary(self):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, patch
        from components.moderation.lexicon_service import inspect_plaintext_write
        import components.moderation.lexicon_service as service

        db = SimpleNamespace(get=AsyncMock())
        with patch.object(service, "_state", AsyncMock(return_value=SimpleNamespace(mode="off", active_revision=2))):
            await inspect_plaintext_write(db, "message", surface="messenger_plaintext", operation="edit")
        db.get.assert_not_awaited()

    async def test_rejects_unsupported_surface_without_database_access(self):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock
        from components.moderation.lexicon_service import inspect_plaintext_write

        with self.assertRaises(ValueError):
            await inspect_plaintext_write(SimpleNamespace(), "x", surface="e2ee", operation="edit")


if __name__ == "__main__":
    unittest.main()
