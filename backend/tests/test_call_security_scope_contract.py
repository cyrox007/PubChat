import os
import unittest
from unittest.mock import patch

from views.calls.routers import _ice_config
from views.calls.ws_handlers import CALL_REASONS, _safe_signal_payload


class CallSecurityScopeContractTests(unittest.TestCase):
    def test_ice_config_has_explicit_non_verified_e2ee_claim(self):
        with patch.dict(
            os.environ,
            {
                "CALL_ICE_STUN_URLS": "stun:example.test:3478",
                "CALL_ICE_TURN_URLS": "",
                "CALL_ICE_PRIVACY_MODE": "false",
            },
            clear=False,
        ):
            payload = _ice_config("00000000-0000-0000-0000-000000000001", now=1_700_000_000)

        security = payload["security"]
        self.assertEqual(security["media_transport"], "webrtc-dtls-srtp")
        self.assertTrue(security["media_encrypted"])
        self.assertFalse(security["signaling_e2ee"])
        self.assertFalse(security["device_identity_bound"])
        self.assertFalse(security["verified_application_e2ee"])
        self.assertEqual(security["claim"], "transport-encrypted-unverified")
        self.assertEqual(payload["media_security"], "webrtc-dtls-srtp")
        self.assertFalse(payload["signaling_e2ee"])

    def test_security_unavailable_is_an_allowlisted_decline_reason(self):
        self.assertIn("security_unavailable", CALL_REASONS)
        payload = _safe_signal_payload(
            {
                "action": "call_decline",
                "call_uid": "00000000-0000-0000-0000-000000000123",
                "reason": "security_unavailable",
            }
        )
        self.assertEqual(payload["reason"], "security_unavailable")

    def test_arbitrary_security_metadata_is_not_forwarded_in_signaling(self):
        payload = _safe_signal_payload(
            {
                "action": "call_offer",
                "call_uid": "00000000-0000-0000-0000-000000000123",
                "mode": "audio",
                "sdp": {"type": "offer", "sdp": "v=0\r\n"},
                "verified_e2ee": True,
                "peer_fingerprint": "attacker-controlled",
            }
        )
        self.assertNotIn("verified_e2ee", payload)
        self.assertNotIn("peer_fingerprint", payload)


if __name__ == "__main__":
    unittest.main()
