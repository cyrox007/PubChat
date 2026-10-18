"""Privacy and calendar contracts for opt-in friend birthday reminders."""
from datetime import date

from components.identity.model import Persona, PrivacySettings
from components.identity.schemas import PersonaUpdateRequest, PrivacyUpdateRequest
from components.notification.birthday import birthday_occurs_on
from components.notification.message_delivery import DEFAULT_MESSAGE_NOTIFICATION_PREFERENCES
from components.notification.schemas import MessageNotificationPreferenceUpdateRequest
from components.identity.service import persona_projection
import pytest
from pydantic import ValidationError


def test_february_29_policy_does_not_shift_a_leap_year_birthday():
    born = date(2000, 2, 29)
    assert birthday_occurs_on(born, date(2025, 2, 28))
    assert not birthday_occurs_on(born, date(2024, 2, 28))
    assert birthday_occurs_on(born, date(2024, 2, 29))
    assert not birthday_occurs_on(born, date(2025, 3, 1))


def test_non_birthday_dates_do_not_create_reminders():
    assert birthday_occurs_on(date(2001, 10, 18), date(2026, 10, 18))
    assert not birthday_occurs_on(date(2001, 10, 18), date(2026, 10, 17))


def test_user_birth_date_never_leaks_from_public_persona_projection():
    person = Persona(handle="someone", display_name="Участник", date_of_birth=date(1995, 10, 18))
    exposed = persona_projection(person)
    assert "date_of_birth" not in exposed
    assert "age" not in exposed


def test_sharing_and_reminders_default_off():
    assert PrivacySettings().share_birthday_with_friends is None or not PrivacySettings().share_birthday_with_friends
    assert DEFAULT_MESSAGE_NOTIFICATION_PREFERENCES["friend_birthday_reminders"] is False
    assert PrivacyUpdateRequest(share_birthday_with_friends=True).share_birthday_with_friends is True
    assert MessageNotificationPreferenceUpdateRequest(friend_birthday_reminders=True).friend_birthday_reminders is True


def test_date_of_birth_validation_rejects_future_birthdays():
    assert PersonaUpdateRequest(date_of_birth=date(1997, 5, 1)).date_of_birth == date(1997, 5, 1)
    with pytest.raises(ValidationError):
        PersonaUpdateRequest(date_of_birth=date(2099, 1, 1))
    with pytest.raises(ValidationError):
        PersonaUpdateRequest(date_of_birth=date(1899, 1, 1))
