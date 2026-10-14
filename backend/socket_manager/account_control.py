from __future__ import annotations

import asyncio
from uuid import UUID

from components.realtime import realtime_service
from settings import config
from utils.logger import setup_logger

logger = setup_logger(__name__)

ACCOUNT_RESTRICTED_CLOSE_CODE = 4003


async def _close_restricted_socket(websocket, *, reason: str) -> None:
    try:
        await asyncio.wait_for(
            websocket.close(code=ACCOUNT_RESTRICTED_CLOSE_CODE, reason=reason),
            timeout=config.REALTIME_SEND_TIMEOUT_SECONDS,
        )
    except Exception:
        pass


def install_account_control(private_manager, room_manager, call_manager=None) -> None:
    async def handle_account_control(event: dict) -> None:
        if event.get("kind") != "account_control" or event.get("action") != "disconnect_account":
            return
        try:
            user_uid = UUID(str(event["user_uid"]))
        except (KeyError, TypeError, ValueError):
            return

        reason = str(event.get("reason") or "Account access restricted")[:120]

        # Keep the Messenger disconnect hook explicit. account.access contract tests
        # intentionally guard this concrete enforcement point so future realtime
        # refactors cannot accidentally leave private-message sockets connected.
        for websocket in list(private_manager.user_connections.get(user_uid, [])):
            await _close_restricted_socket(websocket, reason=reason)
            await private_manager.disconnect(websocket)

        # Calls use their own signaling manager but are governed by the same
        # Account-level restriction. Keep this separate from Messenger so adding or
        # replacing call transport cannot weaken the established DM enforcement hook.
        if call_manager is not None:
            for websocket in list(call_manager.user_connections.get(user_uid, [])):
                await _close_restricted_socket(websocket, reason=reason)
                await call_manager.disconnect(websocket)

        for room_uid, connections in list(room_manager.room_connections.items()):
            for websocket, connection_user_uid in list(connections):
                if connection_user_uid != user_uid:
                    continue
                await _close_restricted_socket(websocket, reason=reason)
                await room_manager.disconnect(websocket, room_uid)

        logger.info("Disconnected realtime sockets for restricted account=%s", user_uid)

    realtime_service.register_callback(handle_account_control)
