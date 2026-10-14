from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, Field, ValidationError

from components.transcription.settings import transcription_config


class TranscriptionSegment(BaseModel):
    start: float = Field(ge=0)
    end: float = Field(ge=0)
    text: str = Field(min_length=1, max_length=4000)


class TranscriptionResult(BaseModel):
    text: str = Field(min_length=1, max_length=200000)
    language: str | None = Field(default=None, max_length=16)
    segments: list[TranscriptionSegment] = Field(default_factory=list)


class TranscriptionProviderError(RuntimeError):
    pass


class TranscriptionProvider(Protocol):
    key: str
    model_name: str | None

    async def transcribe(self, *, media_url: str, surface: str, message_uid: str) -> TranscriptionResult:
        ...


@dataclass(slots=True)
class HttpJsonTranscriptionProvider:
    endpoint: str
    api_key: str = ""
    model_name: str | None = None
    timeout_seconds: float = 60.0
    key: str = "http_json"

    def _request_sync(self, payload: dict) -> dict:
        headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "PubChat-STT/1.0"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read(1024 * 1024)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
            raise TranscriptionProviderError("provider_request_failed") from exc
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TranscriptionProviderError("provider_invalid_json") from exc
        if not isinstance(parsed, dict):
            raise TranscriptionProviderError("provider_invalid_envelope")
        return parsed.get("transcription", parsed)

    async def transcribe(self, *, media_url: str, surface: str, message_uid: str) -> TranscriptionResult:
        payload = {
            "task": "pubchat_media_transcription",
            "schema_version": "v1",
            "model": self.model_name,
            "media_url": media_url,
            "surface": surface,
            "message_uid": message_uid,
        }
        raw = await asyncio.to_thread(self._request_sync, payload)
        try:
            return TranscriptionResult.model_validate(raw)
        except ValidationError as exc:
            raise TranscriptionProviderError("provider_invalid_result") from exc


def build_transcription_provider() -> TranscriptionProvider:
    if transcription_config.provider == "http_json" and transcription_config.configured():
        return HttpJsonTranscriptionProvider(
            endpoint=transcription_config.endpoint,
            api_key=transcription_config.api_key,
            model_name=transcription_config.model or None,
            timeout_seconds=transcription_config.timeout_seconds,
        )
    raise TranscriptionProviderError("provider_not_configured")
