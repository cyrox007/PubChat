import unittest
from uuid import uuid4

from pydantic import ValidationError
from app import app
from components.identity.schemas import PersonaCreateRequest
from components.identity.model import IdentitySession, Persona
from components.identity.service import persona_projection


class MultiPersonaContractTests(unittest.TestCase):
    def test_routes(self):
        paths = {route.path for route in app.routes}
        self.assertIn("/identity/v2/personas", paths)
        self.assertIn("/identity/v2/personas/{persona_uid}/activate", paths)

    def test_extra_privileged_fields_not_in_create_dto(self):
        request = PersonaCreateRequest.model_validate({
            "handle": "persona.alt", "is_primary": True,
            "account_uid": str(uuid4()), "trust_level": "trusted",
        })
        self.assertEqual(
            set(request.model_dump()), {"handle", "display_name", "bio", "social_intent"}
        )

    def test_handle_constraints(self):
        for name in ("a", "invalid handle", "x" * 33):
            with self.assertRaises(ValidationError):
                PersonaCreateRequest(handle=name)

    def test_public_persona_projection(self):
        persona = Persona(
            uid=uuid4(), account_uid=uuid4(),
            handle="alt", display_name="Secondary", social_intent="friends",
            is_primary=False,
        )
        data = persona_projection(persona)
        self.assertNotIn("account_uid", data)
        self.assertNotIn("trust_level", data)
        self.assertFalse(data["is_primary"])

    def test_selection_stored_per_session(self):
        self.assertIn("active_persona_uid", IdentitySession.__table__.columns)
        self.assertNotIn("active_persona_uid", Persona.__table__.columns)


if __name__ == "__main__":
    unittest.main()
