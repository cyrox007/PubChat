import unittest

from app import create_app
from components.message.e2ee_model import PrivateMessageEnvelope
from components.message.e2ee_service import E2EE_VERSION, MAX_ENVELOPE_CIPHERTEXT_BYTES, MAX_SESSION_COUNTER


class MessengerE2EEContractTests(unittest.TestCase):
    def test_envelope_schema_contains_ciphertext_not_plaintext(self):
        columns = set(PrivateMessageEnvelope.__table__.c.keys())
        self.assertIn("ciphertext", columns)
        self.assertIn("nonce", columns)
        self.assertIn("session_id", columns)
        self.assertIn("counter", columns)
        self.assertIn("recipient_device_uid", columns)
        self.assertNotIn("text", columns)
        self.assertNotIn("content", columns)
        self.assertNotIn("plaintext", columns)

    def test_envelope_has_device_and_ratchet_replay_uniqueness(self):
        constraints = {
            constraint.name
            for constraint in PrivateMessageEnvelope.__table__.constraints
            if constraint.name
        }
        self.assertIn("uq_private_message_envelope_message_device", constraints)
        self.assertIn("uq_private_message_envelope_session_counter", constraints)

    def test_protocol_bounds_are_explicit(self):
        self.assertEqual(E2EE_VERSION, "pubchat-e2ee-v1")
        self.assertGreaterEqual(MAX_ENVELOPE_CIPHERTEXT_BYTES, 4096)
        self.assertEqual(MAX_SESSION_COUNTER, 2_147_483_647)

    def test_e2ee_routes_are_installed(self):
        paths = {route.path for route in create_app().routes}
        self.assertIn("/crypto/v1/accounts/{target_account_uid}/devices", paths)
        self.assertIn("/crypto/v1/messages", paths)
        self.assertIn("/crypto/v1/messages/envelopes", paths)


if __name__ == "__main__":
    unittest.main()
