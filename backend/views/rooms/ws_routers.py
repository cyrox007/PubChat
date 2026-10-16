from uuid import UUID

from fastapi import APIRouter, FastAPI, WebSocket, status

from utils.logger import setup_logger
from views.realtime.ws_auth import authenticate_websocket
from views.rooms.ws_typing import handle_websocket_connection

logger = setup_logger(__name__)


def install(app: FastAPI):
    router = APIRouter(prefix="/ws/v2")

    @router.websocket("/rooms/{room_uid}")
    async def websocket_endpoint(websocket: WebSocket, room_uid: UUID):
        user = await authenticate_websocket(
            websocket=websocket,
            target="room",
            resource_uid=room_uid,
        )
        if not user:
            return

        try:
            await handle_websocket_connection(websocket, room_uid, user)
        except Exception as exc:
            logger.exception("Room WebSocket error for %s: %s", room_uid, exc)
            try:
                await websocket.close(
                    code=status.WS_1011_INTERNAL_ERROR,
                    reason="Realtime room error",
                )
            except Exception:
                pass

    app.include_router(router)
