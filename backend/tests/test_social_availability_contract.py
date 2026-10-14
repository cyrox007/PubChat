import unittest
from datetime import datetime, timedelta

from pydantic import ValidationError

from components.social.availability import SocialAvailabilityRequest, availability_projection
from components.social.availability_model import PersonaSocialAvailability


class SocialAvailabilityContractTests(unittest.TestCase):
    def test_availability_is_bound_to_persona(self):
        targets = {
            foreign_key.target_fullname
            for foreign_key in PersonaSocialAvailability.__table__.c.persona_uid.foreign_keys
        }
        self.assertEqual(targets, {"personas.uid"})

    def test_active_availability_projection_is_public_and_minimal(self):
        now = datetime.utcnow()
        value = PersonaSocialAvailability(
            intent="open",
            note="Хочу обсудить кино",
            expires_at=now + timedelta(hours=2),
            updated_at=now,
        )
        projection = availability_projection(value, now=now)
        self.assertEqual(projection["intent"], "open")
        self.assertEqual(projection["note"], "Хочу обсудить кино")
        self.assertIn("expires_at", projection)
        self.assertNotIn("persona_uid", projection)

    def test_expired_availability_is_not_projected(self):
        now = datetime.utcnow()
        value = PersonaSocialAvailability(
            intent="meet",
            note=None,
            expires_at=now - timedelta(seconds=1),
            updated_at=now - timedelta(hours=1),
        )
        self.assertIsNone(availability_projection(value, now=now))

    def test_duration_is_bounded(self):
        SocialAvailabilityRequest(intent="open", duration_minutes=15)
        SocialAvailabilityRequest(intent="games", duration_minutes=480)
        with self.assertRaises(ValidationError):
            SocialAvailabilityRequest(intent="open", duration_minutes=14)
        with self.assertRaises(ValidationError):
            SocialAvailabilityRequest(intent="open", duration_minutes=481)


if __name__ == "__main__":
    unittest.main()
