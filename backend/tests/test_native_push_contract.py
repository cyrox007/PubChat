import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from app import create_app
from components.notification.message_delivery import message_delivery_policy
from components.notification.model import NativePushDevice
from components.notification.native_push import (
    build_messenger_native_push_payload,
    token_fingerprint,
)
from components.notification.native_push_config import validate_fcm_configuration
from components.notification.schemas import NativePushDeviceUpsertRequest
from workers.native_push_delivery import build_parser


class NativePushContractTests(unittest.TestCase):
    def test_payload_is_privacy_minimal(self):
        payload = build_messenger_native_push_payload()
        self.assertEqual(payload["type"], "messenger")
        self.assertEqual(payload["url"], "/messenger")
        self.assertNotIn("message", payload)
        self.assertNotIn("content", payload)
        self.assertNotIn("sender", payload)
        serialized = str(payload).lower()
        self.assertNotIn("ciphertext", serialized)
        self.assertNotIn("filename", serialized)

    def test_token_fingerprint_is_deterministic_and_not_token(self):
        token = "native-registration-token-1234567890"
        digest = token_fingerprint(token)
        self.assertEqual(digest, token_fingerprint(token))
        self.assertNotEqual(digest, token)
        self.assertEqual(len(digest), 64)

    def test_android_registration_requires_explicit_provider_contract(self):
        payload = NativePushDeviceUpsertRequest.model_validate(
            {
                "installation_uid": str(uuid4()),
                "platform": "android",
                "provider": "fcm",
                "token": "x" * 32,
                "device_label": "Android",
                "app_version": "1.0.0",
            }
        )
        self.assertEqual(payload.provider, "fcm")
        self.assertEqual(payload.platform, "android")

    def test_native_token_is_credential_not_projection_contract(self):
        columns = set(NativePushDevice.__table__.c.keys())
        self.assertIn("token", columns)
        self.assertIn("token_hash", columns)
        self.assertIn("revoked_at", columns)

    def test_native_push_policy_is_opt_in_and_offline_only(self):
        offline = message_delivery_policy(
            "messenger",
            online=False,
            active_context=False,
            preferences={"native_push_messenger": True},
        )
        self.assertTrue(offline["native_push_eligible"])
        self.assertTrue(offline["external_eligible"])

        online = message_delivery_policy(
            "messenger",
            online=True,
            active_context=False,
            preferences={"native_push_messenger": True},
        )
        self.assertFalse(online["native_push_eligible"])

        default = message_delivery_policy("messenger", online=False, active_context=False)
        self.assertFalse(default["native_push_eligible"])

    def test_fcm_preflight_requires_all_server_credentials(self):
        with patch.dict(os.environ, {}, clear=False):
            for key in ("FCM_PROJECT_ID", "FCM_SERVICE_ACCOUNT_EMAIL", "FCM_SERVICE_ACCOUNT_PRIVATE_KEY"):
                os.environ.pop(key, None)
            result = validate_fcm_configuration()
        self.assertFalse(result["configured"])
        self.assertFalse(result["valid"])
        self.assertIn("fcm_project_id_missing", result["errors"])
        self.assertIn("fcm_service_account_email_missing", result["errors"])
        self.assertIn("fcm_private_key_missing", result["errors"])

    def test_fcm_preflight_validates_rs256_private_key_without_network(self):
        env = {
            "FCM_PROJECT_ID": "pubchat-android-prod",
            "FCM_SERVICE_ACCOUNT_EMAIL": "push@pubchat-android-prod.iam.gserviceaccount.com",
            "FCM_SERVICE_ACCOUNT_PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----\\nexample\\n-----END PRIVATE KEY-----",
        }
        with patch.dict(os.environ, env, clear=False), patch(
            "components.notification.native_push_config.jwt.encode",
            return_value="signed-local-assertion",
        ) as encode:
            result = validate_fcm_configuration()
        self.assertTrue(result["configured"])
        self.assertTrue(result["valid"])
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["transport"], "fcm-http-v1")
        encode.assert_called_once()

    def test_fcm_preflight_rejects_invalid_private_key(self):
        env = {
            "FCM_PROJECT_ID": "pubchat-android-prod",
            "FCM_SERVICE_ACCOUNT_EMAIL": "push@pubchat-android-prod.iam.gserviceaccount.com",
            "FCM_SERVICE_ACCOUNT_PRIVATE_KEY": "not-a-private-key",
        }
        with patch.dict(os.environ, env, clear=False), patch(
            "components.notification.native_push_config.jwt.encode",
            side_effect=ValueError("invalid key"),
        ):
            result = validate_fcm_configuration()
        self.assertTrue(result["configured"])
        self.assertFalse(result["valid"])
        self.assertEqual(result["errors"], ["fcm_private_key_invalid"])

    def test_worker_exposes_offline_config_preflight(self):
        args = build_parser().parse_args(["--check-config"])
        self.assertTrue(args.check_config)

    def test_native_push_routes_are_installed(self):
        paths = {route.path for route in create_app().routes}
        self.assertIn("/notifications/v1/native-push/config", paths)
        self.assertIn("/notifications/v1/native-push/devices", paths)
        self.assertIn("/notifications/v1/native-push/devices/remove", paths)


if __name__ == "__main__":
    unittest.main()
