import unittest
from uuid import uuid4

from components.message.reaction_model import MessageReaction
from components.transcription.model import MediaTranscriptionJob
from components.transcription.provider import TranscriptionResult
from components.transcription.service import _media_url, _with_transcription
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
                "sdp": {"type": "offer", "sdp": "v=0"},
                "ignored": "do-not-forward",
            }
        )
        self.assertEqual(payload["signal_type"], "call_offer")
        self.assertEqual(payload["mode"], "video")
        self.assertNotIn("ignored", payload)

    def test_call_signaling_rejects_oversized_payloads(self):
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
