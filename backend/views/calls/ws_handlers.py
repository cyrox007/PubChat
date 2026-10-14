from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from components.decorators.db import get_session
from components.moderation.policy import assert_allowed
from socket_manager import call_manager
from utils.logger import setup_logger
from views.messenger.ws_handlers import _dm_allowed


logger = setup_logger(__name__)
CALL_ACTIONS = {"call_offer", "call_answer", "call_ice", "call_ringing", "call_decline", "call_end"}
MAX_SDP_CHARS = 64_000
MAX_ICE_CHARS = 8_000


def _safe_signal_payload(data: dict) -> dict:
    action = str(data.get("action") or "")
    if action not in CALL_ACTIONS:
        raise ValueError("unsupported_call_action")
    call_uid = str(data.get("call_uid") or "")[:64]
    if not call_uid:
        raise ValueError("call_uid_required")
    payload = {
        "type": "call_signal",
        "signal_type": action,
        "call_uid": call_uid,
    }
    if action in {"call_offer", "call_answer"}:
        sdp = data.get("sdp")
        if not isinstance(sdp, dict) or len(str(sdp)) > MAX_SDP_CHARS:
            raise ValueError("invalid_sdp")
        payload["sdp"] = sdp
    if action == "call_ice":
        candidate = data.get("candidate")
        if not isinstance(candidate, dict) or len(str(candidate)) > MAX_ICE_CHARS:
            raise ValueError("invalid_ice_candidate")
        payload["candidate"] = candidate
    if action == "call_offer":
        mode = str(data.get("mode") or "audio")
        payload["mode"] = mode if mode in {"audio", "video"} else "audio"
    if action in {"call_decline", "call_end"}:
        payload["reason"] = str(data.get("reason") or "")[:80]
    return payload


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
        await assert_allowed(db, user_uid, "messenger.send")
    except HTTPException:
        await websocket.send_json({"type": "call_error", "error_type": "calling_restricted"})
        return
    if not await _dm_allowed(db, user_uid, target_uid):
        await websocket.send_json({"type": "call_error", "error_type": "call_not_allowed"})
        return
    try:
        payload = _safe_signal_payload(data)
    except ValueError as exc:
        await websocket.send_json({"type": "call_error", "error_type": str(exc)})
        return
    payload["from_uid"] = str(user_uid)
    await call_manager.send_to_user(target_uid, payload)
    await call_manager.send_to_specific_user(
        websocket,
        {"type": "call_signal_ack", "signal_type": payload["signal_type"], "call_uid": payload["call_uid"]},
    )


@get_session
async def handle_call_connection(websocket: WebSocket, user: dict, db_session: AsyncSession = None):
    user_uid = UUID(str(user["user_uid"]))
    connected = False
    try:
        await call_manager.connect_to_messenger(websocket, user_uid)
        connected = True
        while True:
            data = await websocket.receive_json()
            if data.get("type") in {"heartbeat", "pong"} or data.get("action") == "heartbeat":
                await call_manager.touch_connection(websocket)
                continue
            await call_manager.touch_connection(websocket)
            await _handle_signal(websocket, user_uid, db_session, data)
    except WebSocketDisconnect:
        logger.info("Call signaling disconnected: user=%s", user_uid)
    except Exception:
        logger.exception("Call signaling failed: user=%s", user_uid)
        try:
            await websocket.close(code=1011, reason="Call signaling error")
        except Exception:
            pass
    finally:
        if connected:
            await call_manager.disconnect(websocket)
