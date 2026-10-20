"""Direct Apple Push Notification service adapter (HTTP/2 + ES256).

Only purpose-limited, content-free Messenger/Space reply notifications. This
module never receives message plaintext, session keys or attachment metadata.
"""
from __future__ import annotations

import asyncio
import os
import re
import time
from functools import lru_cache

import httpx
import jwt

from components.notification.native_push import NativePushProviderError, NativePushTarget

_APNS_HOST = "https://api.sandbox.push.apple.com" if os.getenv("APNS_ENVIRONMENT", "production").lower() == "sandbox" else "https://api.push.apple.com"
_VALID_TOKEN = re.compile(r"^[a-fA-F0-9]{32,512}$")
_VALID_KEY_ID = re.compile(r"^[A-Z0-9]{10}$")
_ALLOWED_TYPES = frozenset({"messenger", "space_reply"})


def apns_configured() -> bool:
    return bool(
        os.getenv("APNS_TEAM_ID", "").strip()
        and os.getenv("APNS_KEY_ID", "").strip()
        and os.getenv("APNS_PRIVATE_KEY", "").strip()
        and os.getenv("APNS_TOPIC", "").strip()
        and os.getenv("APNS_ENVIRONMENT", "production").lower() in ("sandbox", "production")
    )


def _apns_token() -> str:
    if not apns_configured():
        raise NativePushProviderError("apns_not_configured", retryable=True)
    team = os.environ["APNS_TEAM_ID"].strip()
    key_id = os.environ["APNS_KEY_ID"].strip()
    if not _VALID_KEY_ID.fullmatch(team) or not _VALID_KEY_ID.fullmatch(key_id):
        raise NativePushProviderError("apns_invalid_key_config", retryable=True)
    key = os.environ["APNS_PRIVATE_KEY"].replace("\\n", "\n")
    try:
        return jwt.encode(
            {"iss": team, "iat": int(time.time())},
            key,
            algorithm="ES256",
            headers={"kid": key_id},
        )
    except Exception as exc:
        raise NativePushProviderError("apns_key_unusable", retryable=True) from exc


class APNsProvider:
    def __init__(self) -> None:
        self._cached: str | None = None
        self._issued_at: float = 0

    @property
    def configured(self) -> bool:
        return apns_configured()

    def _authorization(self) -> str:
        # Apple requires an ES256 token no older than 1h; refresh at 45min.
        if self._cached and time.time() - self._issued_at < 45 * 60:
            return self._cached
        token = _apns_token()
        self._cached, self._issued_at = token, time.time()
        return token

    @staticmethod
    def _classify(status: int, reason: str) -> NativePushProviderError:
        if status == 410 or reason in {"BadDeviceToken", "DeviceTokenNotForTopic", "Unregistered"}:
            return NativePushProviderError("apns_device_invalid", retryable=False, terminal_device=True)
        if status in {408, 425, 429, 500, 502, 503, 504}:
            return NativePushProviderError("apns_temporarily_unavailable", retryable=True)
        if status in {401, 403}:
            return NativePushProviderError("apns_auth_invalid", retryable=True)
        return NativePushProviderError("apns_rejected", retryable=False)

    async def send(self, target: NativePushTarget, payload: dict[str, str]) -> str:
        if target.platform != "ios" or target.provider != "apns":
            raise NativePushProviderError("apns_wrong_provider", retryable=False)
        if not self.configured:
            raise NativePushProviderError("apns_not_configured", retryable=True)
        if not _VALID_TOKEN.fullmatch(target.token) or len(target.token) % 2:
            raise NativePushProviderError("apns_invalid_token", retryable=False, terminal_device=True)
        if payload.get("type") not in _ALLOWED_TYPES:
            raise NativePushProviderError("apns_unapproved_event", retryable=False)
        topic = os.environ["APNS_TOPIC"].strip()
        if not re.fullmatch(r"[A-Za-z0-9.-]{3,128}", topic):
            raise NativePushProviderError("apns_bad_topic", retryable=True)
        # No raw message content, recipient identities, user-provided URLs or cryptographic metadata.
        is_reply = payload["type"] == "space_reply"
        aps = {
            "alert": {
                "title": "Ответ в пространстве PubChat" if is_reply else "Новое сообщение PubChat",
                "body": "Ответили на ваше сообщение." if is_reply else "У вас есть новое личное сообщение.",
            },
            "sound": "pubchat_space.caf" if is_reply else "pubchat_private.caf",
            "thread-id": "pubchat-space-replies" if is_reply else "pubchat-messenger",
        }
        # Client falls back to OS default sound if a custom file is not packaged.
        # This is only first-party alert text; no untrusted message data crosses APNs.
        body = {"aps": aps, "type": payload["type"]}
        if is_reply:
            room_uid = payload.get("room_uid", "")
            try:
                from uuid import UUID
                body["room_uid"] = str(UUID(room_uid))
            except (TypeError, ValueError, AttributeError):
                raise NativePushProviderError("apns_invalid_room", retryable=False)
        url = f"{_APNS_HOST}/3/device/{target.token.lower()}"
        headers = {
            "authorization": f"bearer {self._authorization()}",
            "apns-topic": topic,
            "apns-push-type": "alert",
            "apns-priority": "10",
            "apns-expiration": str(int(time.time()) + 3600),
        }
        try:
            async with httpx.AsyncClient(http2=True, timeout=12.0) as client:
                response = await client.post(url, json=body, headers=headers)
        except (httpx.TransportError, httpx.TimeoutException) as exc:
            raise NativePushProviderError("apns_transport_unavailable", retryable=True) from exc
        if response.status_code != 200:
            try:
                reason = str(response.json().get("reason") or "")
            except (ValueError, TypeError):
                reason = ""
            raise self._classify(response.status_code, reason)
        return str(response.headers.get("apns-id") or "apns-accepted")[:180]


apns_provider = APNsProvider()
