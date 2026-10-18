"""Privacy/calendar contracts for opt-in friend birthday reminders."""
import asyncio
import unittest
from types import SimpleNamespace
from uuid import UUID

from sqlalchemy.dialects import postgresql
from datetime import date

from pydantic import ValidationError

from components.identity.model import Persona, PrivacySettings
from components.identity.schemas import PersonaUpdateRequest, PrivacyUpdateRequest
from components.identity.service import persona_projection
from components.notification.birthday import birthday_occurs_on, sync_friend_birthdays
from components.notification.message_delivery import DEFAULT_MESSAGE_NOTIFICATION_PREFERENCES
from components.notification.schemas import MessageNotificationPreferenceUpdateRequest


class FriendBirthdayContractTests(unittest.TestCase):
    def test_candidate_query_separately_checks_mutual_friend_and_blocks(self):
        class Session:
            statement = None
            commits = 0
            async def get(self, model, uid, *, with_for_update=False):
                if model.__name__ == "MessageNotificationPreference":
                    assert with_for_update
                    return SimpleNamespace(friend_birthday_reminders=True)
                raise AssertionError("Unexpected model")

            async def execute(self, statement):
                self.statement = statement
                return SimpleNamespace(
                    scalars=lambda: SimpleNamespace(all=lambda: [])
                )

            async def commit(self):
                self.commits += 1

        session = Session()
        count = asyncio.run(sync_friend_birthdays(
            session, UUID("00000000-0000-0000-0000-000000000001")
        ))
        self.assertEqual(count, 0)
        self.assertEqual(session.commits, 1)
        sql = str(session.statement.compile(dialect=postgresql.dialect()))
        # FORWARD, RECIPROCAL and BLOCK must be three independent aliases.
        self.assertGreaterEqual(sql.count("account_relationships AS"), 3)
        self.assertIn("FOR UPDATE OF privacy_settings", sql)

    def test_february_29_policy(self):
        born = date(2000, 2, 29)
        self.assertTrue(birthday_occurs_on(born, date(2025, 2, 28)))
        self.assertFalse(birthday_occurs_on(born, date(2024, 2, 28)))
        self.assertTrue(birthday_occurs_on(born, date(2024, 2, 29)))
        self.assertFalse(birthday_occurs_on(born, date(2025, 3, 1)))

    def test_non_birthday_dates(self):
        self.assertTrue(birthday_occurs_on(date(2001, 10, 18), date(2026, 10, 18)))
        self.assertFalse(birthday_occurs_on(date(2001, 10, 18), date(2026, 10, 17)))

    def test_private_date_never_leaks_from_public_persona(self):
        person = Persona(handle="someone", display_name="Участник", date_of_birth=date(1995, 10, 18))
        exposed = persona_projection(person)
        self.assertNotIn("date_of_birth", exposed)
        self.assertNotIn("age", exposed)

    def test_two_separate_opt_in_flags(self):
        self.assertFalse(bool(PrivacySettings().share_birthday_with_friends))
        self.assertFalse(DEFAULT_MESSAGE_NOTIFICATION_PREFERENCES["friend_birthday_reminders"])
        self.assertTrue(PrivacyUpdateRequest(share_birthday_with_friends=True).share_birthday_with_friends)
        self.assertTrue(MessageNotificationPreferenceUpdateRequest(friend_birthday_reminders=True).friend_birthday_reminders)

    def test_reject_future_and_unreasonably_old_dob(self):
        self.assertEqual(PersonaUpdateRequest(date_of_birth=date(1997, 5, 1)).date_of_birth, date(1997, 5, 1))
        with self.assertRaises(ValidationError):
            PersonaUpdateRequest(date_of_birth=date(2099, 1, 1))
        with self.assertRaises(ValidationError):
            PersonaUpdateRequest(date_of_birth=date(1899, 1, 1))


if __name__ == "__main__":
    unittest.main()
