"""Privacy/calendar contracts for opt-in friend birthday reminders."""
import unittest
from datetime import date

from pydantic import ValidationError

from components.identity.model import Persona, PrivacySettings
from components.identity.schemas import PersonaUpdateRequest, PrivacyUpdateRequest
from components.identity.service import persona_projection
from components.notification.birthday import birthday_occurs_on
from components.notification.message_delivery import DEFAULT_MESSAGE_NOTIFICATION_PREFERENCES
from components.notification.schemas import MessageNotificationPreferenceUpdateRequest


class FriendBirthdayContractTests(unittest.TestCase):
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
