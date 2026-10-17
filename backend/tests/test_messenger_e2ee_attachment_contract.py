import unittest

from app import create_app
from components.message.e2ee_attachment import MAX_E2EE_ATTACHMENT_CIPHERTEXT_BYTES
from components.message.e2ee_attachment_model import EncryptedPrivateAttachment
from components.message.e2ee_schemas import EncryptedMessageSendRequest


class MessengerE2EEAttachmentContractTests(unittest.TestCase):
    def test_attachment_schema_keeps_private_metadata_out_of_server_database(self):
        columns = set(EncryptedPrivateAttachment.__table__.c.keys())
        self.assertIn("ciphertext_size", columns)
        self.assertIn("ciphertext_sha256", columns)
        self.assertIn("storage_name", columns)
        self.assertIn("message_uid", columns)
        forbidden = {
            "content_key",
            "key",
            "nonce",
            "filename",
            "original_filename",
            "mime_type",
            "media_kind",
            "plaintext",
        }
        self.assertTrue(forbidden.isdisjoint(columns))

    def test_attachment_is_bound_to_at_most_one_private_message(self):
        unique_sets = {
            tuple(column.name for column in constraint.columns)
            for constraint in EncryptedPrivateAttachment.__table__.constraints
            if getattr(constraint, "unique", False) or constraint.__class__.__name__ == "UniqueConstraint"
        }
        self.assertIn(("message_uid",), unique_sets)

    def test_encrypted_message_contract_accepts_optional_attachment_uid(self):
        self.assertIn("attachment_uid", EncryptedMessageSendRequest.model_fields)
        self.assertFalse(EncryptedMessageSendRequest.model_fields["attachment_uid"].is_required())

    def test_attachment_routes_are_installed(self):
        routes = {(route.path, method) for route in create_app().routes for method in getattr(route, "methods", set())}
        path = "/crypto/v1/attachments/{attachment_uid}"
        self.assertIn((path, "POST"), routes)
        self.assertIn((path, "GET"), routes)
        self.assertIn((path, "DELETE"), routes)

    def test_ciphertext_limit_covers_existing_messenger_media_limit(self):
        self.assertGreaterEqual(MAX_E2EE_ATTACHMENT_CIPHERTEXT_BYTES, 24 * 1024 * 1024 + 16)
        self.assertLessEqual(MAX_E2EE_ATTACHMENT_CIPHERTEXT_BYTES, 32 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
