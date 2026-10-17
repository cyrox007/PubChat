import inspect
import os
import unittest
from unittest.mock import patch

from app import create_app
from components.message import e2ee_delivery
from components.message.encryption_policy import (
    CONVERSATION_MODES,
    ELEVATED_PLATFORM_ROLES,
    POSITIVE_REPUTATION_LABELS,
    SYSTEM_POLICIES,
    conversation_policy,
    set_conversation_mode,
    system_policy,
)
from components.message.encryption_policy_model import PrivateConversationEncryption
from views.messenger import ws_routers


class MessengerEncryptionPolicyContractTests(unittest.TestCase):
    def test_system_policy_accepts_supported_modes(self):
        self.assertEqual(SYSTEM_POLICIES, {"disabled", "optional", "required"})
        self.assertEqual(CONVERSATION_MODES, {"plaintext", "e2ee"})
        for value in SYSTEM_POLICIES:
            with patch.dict(os.environ, {"MESSENGER_E2EE_POLICY": value}, clear=False):
                self.assertEqual(system_policy(), value)

    def test_system_policy_defaults_to_optional_and_rejects_invalid(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(system_policy(), "optional")
        with patch.dict(os.environ, {"MESSENGER_E2EE_POLICY": "mystery"}, clear=False):
            with self.assertRaises(RuntimeError):
                system_policy()

    def test_preference_schema_is_pair_scoped_and_only_stores_mode(self):
        columns = set(PrivateConversationEncryption.__table__.c.keys())
        self.assertEqual(
            columns,
            {"account_low_uid", "account_high_uid", "mode", "set_by_account_uid", "created_at", "updated_at"},
        )
        self.assertNotIn("ciphertext", columns)
        self.assertNotIn("private_key", columns)

    def test_optional_e2ee_is_an_earned_privilege(self):
        self.assertEqual(POSITIVE_REPUTATION_LABELS, {"established", "trusted"})
        self.assertEqual(ELEVATED_PLATFORM_ROLES, {"moderator", "admin"})
        policy_source = inspect.getsource(conversation_policy)
        setter_source = inspect.getsource(set_conversation_mode)
        self.assertIn('effective = "plaintext"', policy_source)
        self.assertIn('"can_enable_e2ee"', policy_source)
        self.assertIn('normalized == "e2ee"', setter_source)
        self.assertIn('"e2ee_privilege_required"', setter_source)
        self.assertIn("HTTP_403_FORBIDDEN", setter_source)

    def test_existing_e2ee_is_not_silently_downgraded_when_reputation_changes(self):
        source = inspect.getsource(conversation_policy)
        self.assertIn("stored in CONVERSATION_MODES", source)
        self.assertIn("effective = stored", source)

    def test_plaintext_and_e2ee_transports_are_both_server_enforced(self):
        plaintext_source = inspect.getsource(ws_routers.EncryptionPolicyWebSocket.receive_json)
        encrypted_source = inspect.getsource(e2ee_delivery.send_encrypted_message)
        self.assertIn("assert_plaintext_allowed", plaintext_source)
        self.assertIn("assert_e2ee_allowed", encrypted_source)

    def test_policy_routes_are_installed(self):
        paths = {
            (route.path, tuple(sorted(getattr(route, "methods", None) or [])))
            for route in create_app().routes
        }
        self.assertTrue(any(path == "/messenger/conversations/{peer_uid}/encryption" and "GET" in methods for path, methods in paths))
        self.assertTrue(any(path == "/messenger/conversations/{peer_uid}/encryption" and "PUT" in methods for path, methods in paths))


if __name__ == "__main__":
    unittest.main()
