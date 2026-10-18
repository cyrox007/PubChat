from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from components.decorators.db import get_realtime_session, release_realtime_session
from components.moderation.policy import assert_allowed
from components.realtime import realtime_service
from socket_manager import call_manager
from utils.logger import setup_logger
from views.messenger.ws_handlers import _dm_allowed
from views.calls.pending_offers import save_pending_offer, clear_pending_offer
from views.calls.call_wakeup import wake_android_recipient


logger = setup_logger(__name__)
CALL_ACTIONS = {"call_offer", "call_answer", "call_ice", "call_ringing", "call_decline", "call_end"}
MAX_SDP_CHARS = 64_000
MAX_ICE_CHARS = 8_000
CALL_SIGNAL_LIMIT = 180
CALL_SIGNAL_WINDOW_SECONDS = 10
CALL_OFFER_LIMIT = 6
CALL_OFFER_WINDOW_SECONDS = 60
CALL_REASONS = {"declined", "busy", "ended", "media_unavailable", "security_unavailable", "connection_failed"}


def _normalized_call_uid(value: object) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_call_uid") from exc


def _safe_sdp(value: object, expected_type: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError("invalid_sdp")
    sdp_type = str(value.get("type") or "")
    sdp_text = value.get("sdp")
    if sdp_type != expected_type or not isinstance(sdp_text, str) or not sdp_text or len(sdp_text) > MAX_SDP_CHARS:
        raise ValueError("invalid_sdp")
    # Do not forward caller-controlled metadata alongside SDP. The signaling
    # service only needs the WebRTC description type and body.
    return {"type": sdp_type, "sdp": sdp_text}


def _safe_candidate(value: object) -> dict:
    if not isinstance(value, dict):
        raise ValueError("invalid_ice_candidate")
    candidate = value.get("candidate")
    if not isinstance(candidate, str) or not candidate or len(candidate) > MAX_ICE_CHARS:
        raise ValueError("invalid_ice_candidate")
    sanitized = {"candidate": candidate}
    sdp_mid = value.get("sdpMid")
    if sdp_mid is not None:
        if not isinstance(sdp_mid, str) or len(sdp_mid) > 32:
            raise ValueError("invalid_ice_candidate")
        sanitized["sdpMid"] = sdp_mid
    sdp_mline_index = value.get("sdpMLineIndex")
    if sdp_mline_index is not None:
        if not isinstance(sdp_mline_index, int) or not 0 <= sdp_mline_index <= 32:
            raise ValueError("invalid_ice_candidate")
        sanitized["sdpMLineIndex"] = sdp_mline_index
    username_fragment = value.get("usernameFragment")
    if username_fragment is not None:
        if not isinstance(username_fragment, str) or len(username_fragment) > 256:
            raise ValueError("invalid_ice_candidate")
        sanitized["usernameFragment"] = username_fragment
    return sanitized


def _safe_signal_payload(data: dict) -> dict:
    action = str(data.get("action") or "")
    if action not in CALL_ACTIONS:
        raise ValueError("unsupported_call_action")
    call_uid = _normalized_call_uid(data.get("call_uid"))
    payload = {
        "type": "call_signal",
        "signal_type": action,
        "call_uid": call_uid,
    }
    if action == "call_offer":
        payload["sdp"] = _safe_sdp(data.get("sdp"), "offer")
        payload["ice_restart"] = data.get("ice_restart") is True
        mode = str(data.get("mode") or "audio")
        payload["mode"] = mode if mode in {"audio", "video"} else "audio"
    elif action == "call_answer":
        payload["sdp"] = _safe_sdp(data.get("sdp"), "answer")
    elif action == "call_ice":
        payload["candidate"] = _safe_candidate(data.get("candidate"))
    elif action in {"call_decline", "call_end"}:
        reason = str(data.get("reason") or "")
        payload["reason"] = reason if reason in CALL_REASONS else ("declined" if action == "call_decline" else "ended")
    return payload


async def _allow_call_signal(user_uid: UUID, action: str) -> bool:
    if not await realtime_service.allow_action(
        user_uid,
        "call-signal",
        limit=CALL_SIGNAL_LIMIT,
        window_seconds=CALL_SIGNAL_WINDOW_SECONDS,
    ):
        return False
    if action == "call_offer":
        return await realtime_service.allow_action(
            user_uid,
            "call-offer",
            limit=CALL_OFFER_LIMIT,
            window_seconds=CALL_OFFER_WINDOW_SECONDS,
        )
    return True


async def _handle_signal(websocket: WebSocket, user_uid: UUID, db: AsyncSession, data: dict) -> None:
    try:
        target_uid = UUID(str(data.get("target_uid")))
    except (TypeError, ValueError):
        await websocket.send_json({"type": "call_error", "error_type": "invalid_target"})
        return
    if target_uid == user_uid:
        await websocket.send_json({"type": "call_error", "error_type": "cannot_call_self"})
        return
    try:
        payload = _safe_signal_payload(data)
    except ValueError as exc:
        await websocket.send_json({"type": "call_error", "error_type": str(exc)})
        return
    if not await _allow_call_signal(user_uid, payload["signal_type"]):
        await websocket.send_json({"type": "call_error", "error_type": "call_rate_limited"})
        return
    try:
        await assert_allowed(db, user_uid, "messenger.send")
    except HTTPException:
        await websocket.send_json({"type": "call_error", "error_type": "calling_restricted"})
        return
    if not await _dm_allowed(db, user_uid, target_uid):
        await websocket.send_json({"type": "call_error", "error_type": "call_not_allowed"})
        return

    payload["from_uid"] = str(user_uid)
    # Preserve the validated offer briefly for an Android app opened from
    # a call wakeup. No SDP/ICE travels via FCM or appears in logs.
    if payload["signal_type"] == "call_offer" and not payload.get("ice_restart"):
        try:
            await save_pending_offer(target_uid, payload)
        except Exception:
            logger.warning("Pending call offer storage unavailable")
    elif payload["signal_type"] in {"call_answer", "call_end", "call_decline"}:
        try:
            await clear_pending_offer(target_uid, payload["call_uid"])
            await clear_pending_offer(user_uid, payload["call_uid"])
        except Exception:
            logger.warning("Pending call cleanup unavailable")
    await call_manager.send_to_user(target_uid, payload)
    if payload["signal_type"] == "call_offer" and not payload.get("ice_restart"):
        try:
            await wake_android_recipient(db, target_uid, payload["call_uid"])
        except Exception:
            logger.warning("Call wakeup failed")
    await call_manager.send_to_specific_user(
        websocket,
        {"type": "call_signal_ack", "signal_type": payload["signal_type"], "call_uid": payload["call_uid"]},
    )


@get_realtime_session
async def handle_call_connection(websocket: WebSocket, user: dict, db_session: AsyncSession = None):
    user_uid = UUID(str(user["user_uid"]))
    connected = False
    try:
        await call_manager.connect_to_messenger(websocket, user_uid)
        connected = True
        while True:
            await release_realtime_session(db_session)
            data = await websocket.receive_json()
            if data.get("type") in {"heartbeat", "pong"} or data.get("action") == "heartbeat":
                await call_manager.touch_connection(websocket)
                continue
            await call_manager.touch_connection(websocket)
            await _handle_signal(websocket, user_uid, db_session, data)
    except WebSocketDisconnect:
        logger.info("Call signaling disconnected: user=%s", user_uid)
    except Exception:
        # Never log SDP, ICE candidates or arbitrary signaling payloads here.
        logger.exception("Call signaling failed: user=%s", user_uid)
        try:
            await websocket.close(code=1011, reason="Call signaling error")
        except Exception:
            pass
    finally:
        if connected:
            await call_manager.disconnect(websocket)
