from uuid import UUID

from fastapi import APIRouter, FastAPI, HTTPException, WebSocket, status

from components.message.encryption_policy import assert_plaintext_allowed
from database import Database
from utils.logger import setup_logger
from views.messenger.ws_handlers import handle_messenger_connection
from views.realtime.ws_auth import authenticate_websocket

logger = setup_logger(__name__)


class EncryptionPolicyWebSocket:
    """Consume legacy plaintext send frames that violate conversation policy."""

    def __init__(self, websocket: WebSocket, account_uid: UUID):
        self._websocket = websocket
        self._account_uid = account_uid

    def __getattr__(self, name):
        return getattr(self._websocket, name)

    async def receive_json(self, *args, **kwargs):
        while True:
            data = await self._websocket.receive_json(*args, **kwargs)
            if data.get("action") != "send_message":
                return data
            try:
                receiver_uid = UUID(str(data.get("receiver_uid")))
            except (TypeError, ValueError):
                return data
            try:
                async with Database.sessionmaker() as db:
                    await assert_plaintext_allowed(db, self._account_uid, receiver_uid)
            except HTTPException as exc:
                detail = exc.detail if isinstance(exc.detail, dict) else {"error_type": "conversation_requires_e2ee"}
                await self._websocket.send_json({
                    "type": "error",
                    "frontId": data.get("frontId"),
                    **detail,
                })
                continue
            return data


def install(app: FastAPI):
    router = APIRouter(prefix="/ws/v2")

    @router.websocket("/messenger")
    async def websocket_endpoint(websocket: WebSocket):
        user = await authenticate_websocket(
            websocket=websocket,
            target="messenger",
        )
        if not user:
            return

        try:
            account_uid = UUID(str(user["user_uid"]))
            await handle_messenger_connection(EncryptionPolicyWebSocket(websocket, account_uid), user)
        except Exception as exc:
            logger.exception("Messenger WebSocket error: %s", exc)
            try:
                await websocket.close(
                    code=status.WS_1011_INTERNAL_ERROR,
                    reason="Realtime messenger error",
                )
            except Exception:
                pass

    app.include_router(router)
