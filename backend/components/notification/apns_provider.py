"""Apple Push Notification service HTTP/2 token-auth adapter.

APNs receives only generic message/reply event payloads, never a Messenger
plaintext, username, attachment or ciphertext. Apple credentials are supplied by
the deployment environment; no p8 file is bundled in a repo or mobile app.
"""
from __future__ import annotations

import asyncio
import os
import re
import time
from dataclasses import dataclass

import httpx
import jwt


APNS_TOKEN_PATTERN = re.compile(r"^[0-9a-fA-F]{64,256}$")
APNS_ALLOWED_EVENT_TYPES = frozenset({"messenger", "space_reply"})
APNS_ALLOWED_ENVIRONMENTS = frozenset({"sandbox", "production"})


@dataclass(frozen=True)
class APNsDeliveryError(Exception):
    reason: str
    retryable: bool
    terminal_device: bool = False


def apns_configured() -> bool:
    return bool(
        os.getenv("APNS_TEAM_ID", "").strip()
        and os.getenv("APNS_KEY_ID", "").strip()
        and os.getenv("APNS_PRIVATE_KEY", "").strip()
        and os.getenv("APNS_TOPIC", "").strip()
        and os.getenv("APNS_ENVIRONMENT", "sandbox").strip() in APNS_ALLOWED_ENVIRONMENTS
    )


def apns_endpoint() -> str:
    return ("https://api.push.apple.com" if os.getenv("APNS_ENVIRONMENT", "sandbox") == "production"
            else "https://api.sandbox.push.apple.com")


def apns_notification_payload(payload: dict[str, str]) -> dict:
    kind = payload.get("type")
    if kind not in APNS_ALLOWED_EVENT_TYPES:
        raise ValueError("unsupported_apns_event")
    space_reply = kind == "space_reply"
    sound = "pubchat_space_notification.wav" if space_reply else "pubchat_private_notification.wav"
    aps = {
        "alert": {
            "title": "Ответ в пространстве PubChat" if space_reply else "Новое личное сообщение PubChat",
            "body": "Ответили на ваше сообщение." if space_reply else "У вас есть новое личное сообщение.",
        },
        "sound": sound,
        "thread-id": "pubchat-space-replies" if space_reply else "pubchat-messenger",
    }
    notification = {"aps": aps, "type": kind}
    if space_reply:
        # room_uid is metadata and must always be validated, not parsed from an
        # attacker-controlled URL. Never publish room names or message content.
        from uuid import UUID
        notification["room_uid"] = str(UUID(str(payload["room_uid"])))
    return notification


def classify_apns_error(status: int, reason: str) -> APNsDeliveryError:
    # Device identity is permanently invalid; stop queueing it.
    if reason in {"BadDeviceToken", "DeviceTokenNotForTopic", "Unregistered"} or status == 410:
        return APNsDeliveryError("apns_device_unregistered", retryable=False, terminal_device=True)
    if status in (408, 425, 429, 500, 503) or status >= 500:
        return APNsDeliveryError("apns_provider_unavailable", retryable=True)
    if status in (401, 403):
        return APNsDeliveryError("apns_auth_failure", retryable=True)
    return APNsDeliveryError("apns_delivery_rejected", retryable=False)


class APNsProvider:
    def __init__(self) -> None:
        self._jwt: str | None = None
        self._issued: float = 0

    @property
    def configured(self) -> bool:
        return apns_configured()

    def _authorization(self) -> str:
        if not self.configured:
            raise APNsDeliveryError("apns_not_configured", retryable=False)
        now = time.time()
        if self._jwt and now - self._issued < 2400:
            return self._jwt
        team = os.environ["APNS_TEAM_ID"].strip()
        key_id = os.environ["APNS_KEY_ID"].strip()
        private = os.environ["APNS_PRIVATE_KEY"].replace("\\n", "\n")
        try:
            encoded = jwt.encode(
                {"iss": team, "iat": int(now)},
                private, algorithm="ES256", headers={"kid": key_id},
            )
        except (ValueError, jwt.PyJWTError, TypeError) as exc:
            raise APNsDeliveryError("apns_signing_error", retryable=True) from exc
        self._jwt = encoded
        self._issued = now
        return encoded

    async def send(self, token: str, payload: dict[str, str]) -> str:
        if not APNS_TOKEN_PATTERN.fullmatch(token):
            raise APNsDeliveryError("apns_invalid_device_token", retryable=False, terminal_device=True)
        data = apns_notification_payload(payload)
        headers = {
            "authorization": f"bearer {self._authorization()}",
            "apns-topic": os.environ["APNS_TOPIC"].strip(),
            "apns-push-type": "alert",
            "apns-priority": "10",
            "apns-expiration": "0",
        }
        try:
            async with httpx.AsyncClient(http2=True, timeout=10.0) as client:
                response = await client.post(
                    f"{apns_endpoint()}/3/device/{token.lower()}",
                    headers=headers, json=data,
                )
        except httpx.HTTPError as exc:
            raise APNsDeliveryError("apns_transport_error", retryable=True) from exc
        if response.status_code != 200:
            try:
                reason = str(response.json().get("reason", ""))[:100]
            except (ValueError, AttributeError):
                reason = ""
            raise classify_apns_error(response.status_code, reason)
        return response.headers.get("apns-id", "")[:180]
