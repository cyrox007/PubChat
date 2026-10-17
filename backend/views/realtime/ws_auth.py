import asyncio
from typing import Optional
from uuid import UUID

from fastapi import WebSocket, status
from pydantic import ValidationError
from starlette.websockets import WebSocketDisconnect

from components.identity.service import active_identity_session
from components.moderation.account_access import active_account_access_restriction
from components.realtime import realtime_service
from components.realtime.schemas import RealtimeAuthFrame
from database import Database
from settings import config
from utils.logger import setup_logger

logger = setup_logger(__name__)


async def authenticate_websocket(
    websocket: WebSocket,
    target: str,
    resource_uid: Optional[UUID] = None,
) -> Optional[dict]:
    """
    Accept a WebSocket and authenticate it through the first protocol frame.

    No credential is carried in the URL. The HTTP-issued ticket is short-lived,
    one-time and scoped to the requested realtime target/resource and, for modern
    Identity v2 clients, the exact auth session/device that requested it.
    """
    await websocket.accept()

    try:
        raw_frame = await asyncio.wait_for(
            websocket.receive_json(),
            timeout=config.REALTIME_AUTH_TIMEOUT_SECONDS,
        )
        frame = RealtimeAuthFrame.model_validate(raw_frame)
    except asyncio.TimeoutError:
        await websocket.close(code=4401, reason="Realtime authentication timed out")
        return None
    except WebSocketDisconnect:
        return None
    except (ValidationError, ValueError, TypeError):
        await websocket.close(code=4401, reason="Invalid realtime authentication frame")
        return None
    except Exception:
        logger.exception("Ошибка чтения realtime auth frame")
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Realtime handshake failed")
        return None

    ticket_payload = await realtime_service.consume_ticket(
        raw_ticket=frame.ticket,
        target=target,
        resource_uid=resource_uid,
    )
    if not ticket_payload:
        await websocket.close(code=4401, reason="Invalid or expired realtime ticket")
        return None

    session = await Database.get_session()
    try:
        restriction = await active_account_access_restriction(
            session,
            ticket_payload["account_uid"],
        )
        if restriction is not None:
            await websocket.close(code=4003, reason="Account access restricted")
            return None

        session_uid = ticket_payload.get("session_uid")
        device_uid = ticket_payload.get("device_uid")
        if session_uid:
            identity_session = await active_identity_session(
                session,
                ticket_payload["account_uid"],
                session_uid,
            )
            if not identity_session:
                await websocket.close(code=4401, reason="Session revoked")
                return None
            if device_uid and str(identity_session.device_uid) != str(device_uid):
                await websocket.close(code=4401, reason="Session device mismatch")
                return None
    finally:
        await session.close()

    user_data = {
        "user_uid": ticket_payload["account_uid"],
        "session_uid": ticket_payload.get("session_uid"),
        "device_uid": ticket_payload.get("device_uid"),
        "realtime_protocol": 2,
        "resume_token": frame.resume_token,
    }
    # Store routing metadata on the concrete socket so every local manager can
    # distinguish several sessions/devices of the same Account without turning
    # the WebSocket connection itself into user identity.
    websocket.state.account_uid = ticket_payload["account_uid"]
    websocket.state.session_uid = ticket_payload.get("session_uid")
    websocket.state.device_uid = ticket_payload.get("device_uid")

    await websocket.send_json(
        {
            "type": "realtime_ready",
            "protocol": 2,
            "target": target,
            "resource_uid": str(resource_uid) if resource_uid else None,
            "heartbeat_seconds": config.REALTIME_HEARTBEAT_SECONDS,
        }
    )
    return user_data
