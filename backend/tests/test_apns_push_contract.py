import asyncio
import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from components.notification.apns_push import APNsProvider, apns_configured
from components.notification.native_push import (
    FCMProvider, NativePushProviderError, NativePushTarget,
    build_messenger_native_push_payload,
)
from components.notification.space_reply_delivery import space_reply_push_payload


class FakeResponse:
    def __init__(self, status=200, reason=None):
        self.status_code = status
        self.headers = {"apns-id": "ios-accepted-uid"}
        self._reason = reason or ""

    def json(self):
        return {"reason": self._reason}


class StubClient:
    def __init__(self, *, http2=False, timeout=None):
        assert http2 is True
        self.records = []
        self.response = FakeResponse()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json, headers):
        self.records.append((url, json, headers))
        TEST_CALLS.append((url, json, headers))
        return self.response


TEST_CALLS = []


class APNsTransportTests(unittest.TestCase):
    def setUp(self):
        TEST_CALLS.clear()
        self.environment = patch.dict(os.environ, {
            "APNS_TEAM_ID": "ABCDE12345",
            "APNS_KEY_ID": "1A2B3C4D5E",
            "APNS_PRIVATE_KEY": "test-setup-no-real-secret",
            "APNS_TOPIC": "ru.pubchat.app",
            "APNS_ENVIRONMENT": "sandbox",
        })
        self.environment.start()

    def tearDown(self):
        self.environment.stop()

    def test_configured_requires_credentials_and_supported_environment(self):
        self.assertTrue(apns_configured())
        with patch.dict(os.environ, {"APNS_PRIVATE_KEY": ""}):
            self.assertFalse(apns_configured())
        with patch.dict(os.environ, {"APNS_ENVIRONMENT": "not-an-apple-environment"}):
            self.assertFalse(apns_configured())

    def test_privacy_safe_messenger_and_space_reply_apns_payload(self):
        async def run():
            provider = APNsProvider()
            ios = NativePushTarget(uid=uuid4(), token="ab" * 32, provider="apns", platform="ios")
            provider._authorization = lambda: "signed-test-token"
            with patch("components.notification.apns_push.httpx.AsyncClient", StubClient):
                self.assertEqual(await provider.send(ios, build_messenger_native_push_payload()), "ios-accepted-uid")
                self.assertEqual(await provider.send(ios, space_reply_push_payload(uuid4())), "ios-accepted-uid")
            self.assertEqual(len(TEST_CALLS), 2)
            for path, body, headers in TEST_CALLS:
                self.assertTrue(path.startswith("https://api.sandbox.push.apple.com/3/device/"))
                self.assertEqual(headers["apns-topic"], "ru.pubchat.app")
                self.assertEqual(headers["apns-push-type"], "alert")
                self.assertEqual(set(body.keys()) - {"aps", "type", "room_uid"}, set())
                self.assertNotIn("ciphertext", str(body).lower())
                self.assertNotIn("user", str(body).lower())
                self.assertNotIn("peer", str(body).lower())
                self.assertIn("sound", body["aps"])
            self.assertEqual(TEST_CALLS[0][1]["aps"]["sound"], "pubchat_private.wav")
            self.assertEqual(TEST_CALLS[1][1]["aps"]["sound"], "pubchat_space.wav")

        asyncio.run(run())

    def test_apns_error_classification_has_safe_retries(self):
        provider = APNsProvider()
        self.assertTrue(provider._classify(410, "Unregistered").terminal_device)
        self.assertTrue(provider._classify(400, "BadDeviceToken").terminal_device)
        self.assertTrue(provider._classify(429, "TooManyRequests").retryable)
        self.assertTrue(provider._classify(503, "Shutdown").retryable)
        self.assertTrue(provider._classify(403, "InvalidProviderToken").retryable)
        self.assertFalse(provider._classify(400, "PayloadTooLarge").retryable)

    def test_malformed_token_provider_and_event_are_rejected(self):
        async def run():
            provider = APNsProvider()
            provider._authorization = lambda: "signed-test-token"
            invalid = [
                NativePushTarget(uid=uuid4(), token="invalid", provider="apns", platform="ios"),
                NativePushTarget(uid=uuid4(), token="aa" * 32, provider="fcm", platform="android"),
            ]
            for target in invalid:
                with self.assertRaises(NativePushProviderError):
                    await provider.send(target, build_messenger_native_push_payload())
            with self.assertRaises(NativePushProviderError):
                await provider.send(
                    NativePushTarget(uid=uuid4(), token="ab" * 32, provider="apns", platform="ios"),
                    {"type": "unsafe", "title": "private data", "body": "content"},
                )
        asyncio.run(run())

    def test_single_worker_provider_dispatch_sends_apns_without_fcm_credentials(self):
        async def run():
            target = NativePushTarget(uid=uuid4(), token="ab" * 32, provider="apns", platform="ios")
            with patch("components.notification.apns_push.apns_provider.send", return_value="ios-accepted") as send:
                result = await FCMProvider().send(target, build_messenger_native_push_payload())
                self.assertEqual(result, "ios-accepted")
                send.assert_awaited_once()
        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
