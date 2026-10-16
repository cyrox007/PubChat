from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, HTTPException

from components.auth.middleware import auth_middle
from settings import config


DEFAULT_DEBUG_STUN = "stun:stun.l.google.com:19302"
MIN_TURN_SECRET_LENGTH = 16


def _csv_env(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def _privacy_mode() -> bool:
    return os.getenv("CALL_ICE_PRIVACY_MODE", "false").strip().lower() in {"1", "true", "yes", "on"}


def _turn_ttl_seconds() -> int:
    return max(300, min(86400, int(os.getenv("CALL_ICE_CREDENTIAL_TTL_SECONDS", "3600"))))


def _turn_credentials(account_uid: UUID | str, now: int | None = None) -> tuple[str, str, int]:
    secret = os.getenv("CALL_ICE_TURN_SHARED_SECRET", "")
    if len(secret) < MIN_TURN_SECRET_LENGTH:
        raise RuntimeError("TURN shared secret is not configured")
    expires_at = int(now or time.time()) + _turn_ttl_seconds()
    username = f"{expires_at}:{account_uid}"
    digest = hmac.new(secret.encode("utf-8"), username.encode("utf-8"), hashlib.sha1).digest()
    credential = base64.b64encode(digest).decode("ascii")
    return username, credential, expires_at


def _ice_config(account_uid: UUID | str, now: int | None = None) -> dict:
    stun_urls = _csv_env("CALL_ICE_STUN_URLS", DEFAULT_DEBUG_STUN if config.DEBUG else "")
    turn_urls = _csv_env("CALL_ICE_TURN_URLS")
    privacy_mode = _privacy_mode()

    if privacy_mode and not turn_urls:
        raise RuntimeError("CALL_ICE_PRIVACY_MODE requires TURN relay URLs")

    servers: list[dict] = []
    if stun_urls and not privacy_mode:
        servers.append({"urls": stun_urls})

    expires_at = None
    if turn_urls:
        username, credential, expires_at = _turn_credentials(account_uid, now=now)
        servers.append(
            {
                "urls": turn_urls,
                "username": username,
                "credential": credential,
            }
        )

    if not servers and not config.DEBUG:
        raise RuntimeError("Production WebRTC ICE configuration is not configured")

    return {
        "ice_servers": servers,
        "ice_transport_policy": "relay" if privacy_mode else "all",
        "credentials_expire_at": expires_at,
        "media_security": "webrtc-dtls-srtp",
        "signaling_e2ee": False,
    }


def install(app: FastAPI) -> None:
    router = APIRouter(prefix="/calls/v1", tags=["calls-v1"])

    @router.get("/ice-config")
    async def ice_config(current_user: dict = Depends(auth_middle)):
        try:
            payload = _ice_config(current_user["user_uid"])
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail={"error_type": "call_ice_unavailable"}) from exc
        return {"status": "ok", **payload}

    app.include_router(router)
