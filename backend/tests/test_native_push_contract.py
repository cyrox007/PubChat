import unittest
from uuid import uuid4

from app import create_app
from components.notification.message_delivery import message_delivery_policy
from components.notification.model import NativePushDevice
from components.notification.native_push import (
    build_messenger_native_push_payload,
    token_fingerprint,
)
from components.notification.schemas import NativePushDeviceUpsertRequest


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

    def test_native_push_is_opt_in_even_when_websocket_stays_online_in_background(self):
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
        self.assertTrue(online["native_push_eligible"])
        self.assertTrue(online["external_eligible"])

        default = message_delivery_policy("messenger", online=False, active_context=False)
        self.assertFalse(default["native_push_eligible"])

    def test_native_push_endpoints_are_unique_and_ios_ready(self):
        import asyncio
        from unittest.mock import patch

        routes = create_app().routes
        for endpoint in ("/config", "/devices", "/devices/remove"):
            matched = [r for r in routes if r.path == "/notifications/v1/native-push" + endpoint]
            # Two overlapping FastAPI paths shadowed the real APNs provider and
            # made iOS fail to decode its required "ios" capability.
            self.assertEqual(len(matched), 1, endpoint)
        config_route = next(r for r in routes if r.path == "/notifications/v1/native-push/config")
        with patch("views.notifications.native_push_routers.fcm_configured", return_value=True), \
             patch("views.notifications.native_push_routers.apns_configured", return_value=True):
            response = asyncio.run(config_route.endpoint(current_user={"user_uid": str(uuid4())}))
        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["android"], {"provider": "fcm", "enabled": True})
        self.assertEqual(response["ios"], {"provider": "apns", "enabled": True})
        self.assertTrue(response["fcm_enabled"])
        self.assertEqual(response["privacy"], {"message_content_in_push": False})

    def test_native_push_routes_are_installed(self):
        paths = {route.path for route in create_app().routes}
        self.assertIn("/notifications/v1/native-push/config", paths)
        self.assertIn("/notifications/v1/native-push/devices", paths)
        self.assertIn("/notifications/v1/native-push/devices/remove", paths)


if __name__ == "__main__":
    unittest.main()
