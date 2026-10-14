from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TranscriptionConfig:
    provider: str
    endpoint: str
    api_key: str
    model: str
    timeout_seconds: float
    max_attempts: int
    batch_size: int

    def configured(self) -> bool:
        return self.provider == "http_json" and bool(self.endpoint)


def load_transcription_config() -> TranscriptionConfig:
    return TranscriptionConfig(
        provider=(os.getenv("TRANSCRIPTION_PROVIDER", "disabled").strip().lower() or "disabled"),
        endpoint=os.getenv("TRANSCRIPTION_ENDPOINT", "").strip(),
        api_key=os.getenv("TRANSCRIPTION_API_KEY", ""),
        model=os.getenv("TRANSCRIPTION_MODEL", "").strip(),
        timeout_seconds=max(1.0, float(os.getenv("TRANSCRIPTION_TIMEOUT_SECONDS", "60"))),
        max_attempts=max(1, min(10, int(os.getenv("TRANSCRIPTION_MAX_ATTEMPTS", "5")))),
        batch_size=max(1, min(100, int(os.getenv("TRANSCRIPTION_BATCH_SIZE", "20")))),
    )


transcription_config = load_transcription_config()
