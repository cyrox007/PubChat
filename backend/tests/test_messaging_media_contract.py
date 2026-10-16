import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from components.message.reaction_model import MessageReaction
from components.transcription.model import MediaTranscriptionJob
from components.transcription.provider import TranscriptionResult
from components.transcription.service import _media_url, _with_transcription
from views.calls.routers import _ice_config, _turn_credentials
from views.calls.ws_handlers import _safe_signal_payload


class MessagingMediaContractTests(unittest.TestCase):
    def test_voice_media_url_prefers_voice_payload(self):
        self.assertEqual(
            _media_url({"voice": "/uploads/voice.webm", "files": [{"url": "/uploads/other.webm"}]}, "voice"),
            "/uploads/voice.webm",
        )

    def test_audio_video_media_url_uses_first_file(self):
        self.assertEqual(_media_url({"files": [{"url": "/uploads/video.webm"}]}, "video"), "/uploads/video.webm")
        self.assertIsNone(_media_url({"files": []}, "audio"))

    def test_transcription_metadata_is_structured(self):
        result = _with_transcription(
            {"duration": 3.5},
            status="ready",
            text="Привет",
            language="ru",
            segments=[{"start": 0, "end": 1, "text": "Привет"}],
        )
        self.assertEqual(result["duration"], 3.5)
        self.assertEqual(result["transcription"]["status"], "ready")
        self.assertEqual(result["transcription"]["text"], "Привет")

    def test_transcription_provider_result_validates_segments(self):
        result = TranscriptionResult.model_validate(
            {
                "text": "Тест",
                "language": "ru",
                "segments": [{"start": 0, "end": 1.2, "text": "Тест"}],
            }
        )
        self.assertEqual(result.segments[0].text, "Тест")

    def test_call_offer_is_sanitized(self):
        call_uid = str(uuid4())
        payload = _safe_signal_payload(
            {
                "action": "call_offer",
                "call_uid": call_uid,
                "mode": "video",
                "sdp": {"type": "offer", "sdp": "v=0", "ignored": "secret"},
                "ignored": "do-not-forward",
            }
        )
        self.assertEqual(payload["signal_type"], "call_offer")
        self.assertEqual(payload["mode"], "video")
        self.assertEqual(payload["sdp"], {"type": "offer", "sdp": "v=0"})
        self.assertNotIn("ignored", payload)

    def test_call_signaling_rejects_invalid_or_oversized_payloads(self):
        with self.assertRaises(ValueError):
            _safe_signal_payload({"action": "call_offer", "call_uid": "not-a-uuid", "sdp": {"type": "offer", "sdp": "v=0"}})
        with self.assertRaises(ValueError):
            _safe_signal_payload({"action": "call_offer", "call_uid": str(uuid4()), "sdp": {"type": "answer", "sdp": "v=0"}})
        with self.assertRaises(ValueError):
            _safe_signal_payload(
                {
                    "action": "call_offer",
                    "call_uid": str(uuid4()),
                    "sdp": {"type": "offer", "sdp": "x" * 70000},
                }
            )
        with self.assertRaises(ValueError):
            _safe_signal_payload(
                {
                    "action": "call_ice",
                    "call_uid": str(uuid4()),
                    "candidate": {"candidate": "x" * 9000},
                }
            )

    def test_call_candidate_is_minimal_and_reason_is_allowlisted(self):
        payload = _safe_signal_payload(
            {
                "action": "call_ice",
                "call_uid": str(uuid4()),
                "candidate": {
                    "candidate": "candidate:1 1 UDP 1 192.0.2.1 40000 typ host",
                    "sdpMid": "0",
                    "sdpMLineIndex": 0,
                    "usernameFragment": "abc",
                    "private": "drop-me",
                },
            }
        )
        self.assertNotIn("private", payload["candidate"])
        ended = _safe_signal_payload(
            {"action": "call_end", "call_uid": str(uuid4()), "reason": "arbitrary user controlled text"}
        )
        self.assertEqual(ended["reason"], "ended")

    @patch.dict(
        os.environ,
        {
            "CALL_ICE_TURN_SHARED_SECRET": "0123456789abcdef0123456789abcdef",
            "CALL_ICE_CREDENTIAL_TTL_SECONDS": "3600",
        },
        clear=False,
    )
    def test_turn_credentials_are_short_lived_and_account_scoped(self):
        account_uid = uuid4()
        username, credential, expires_at = _turn_credentials(account_uid, now=1_700_000_000)
        self.assertEqual(username, f"1700003600:{account_uid}")
        self.assertTrue(credential)
        self.assertEqual(expires_at, 1_700_003_600)

    @patch.dict(
        os.environ,
        {
            "CALL_ICE_STUN_URLS": "stun:stun.example.test:3478",
            "CALL_ICE_TURN_URLS": "turn:turn.example.test:3478?transport=udp,turns:turn.example.test:5349?transport=tcp",
            "CALL_ICE_TURN_SHARED_SECRET": "0123456789abcdef0123456789abcdef",
            "CALL_ICE_PRIVACY_MODE": "true",
        },
        clear=False,
    )
    def test_privacy_mode_forces_relay_and_omits_stun(self):
        config = _ice_config(uuid4(), now=1_700_000_000)
        self.assertEqual(config["ice_transport_policy"], "relay")
        self.assertEqual(len(config["ice_servers"]), 1)
        self.assertTrue(all(str(url).startswith("turn") for url in config["ice_servers"][0]["urls"]))
        self.assertEqual(config["media_security"], "webrtc-dtls-srtp")
        self.assertFalse(config["signaling_e2ee"])

    def test_durable_jobs_and_reactions_are_cross_surface(self):
        job_columns = MediaTranscriptionJob.__table__.c
        reaction_columns = MessageReaction.__table__.c
        self.assertIn("surface", job_columns)
        self.assertIn("message_uid", job_columns)
        self.assertIn("surface", reaction_columns)
        self.assertIn("message_uid", reaction_columns)
        self.assertIn("emoji", reaction_columns)


if __name__ == "__main__":
    unittest.main()
