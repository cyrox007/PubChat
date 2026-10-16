from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, WebSocket
from sqlalchemy.ext.asyncio import AsyncSession

from components.decorators.db import get_session
from components.moderation.policy import assert_allowed
from components.realtime import realtime_service
from socket_manager import room_manager
from views.rooms.ws_handlers import handle_websocket_connection as _handle_websocket_connection


async def relay_typing(
    room_uid: UUID,
    user_uid: UUID,
    db_session: AsyncSession,
    active: object,
) -> None:
    """Relay ephemeral typing state without persisting message input or durable activity."""
    if not isinstance(active, bool):
        return

    try:
        await assert_allowed(
            db_session,
            user_uid,
            "space.chat.send",
            scope_type="space",
            scope_uid=room_uid,
        )
    except HTTPException:
        # Typing is secondary UX state. Restricted users simply stop emitting it;
        # the canonical message-send path remains responsible for user-facing errors.
        return

    allowed = await realtime_service.allow_action(
        user_uid=user_uid,
        bucket=f"space-typing:{room_uid}",
        limit=20,
        window_seconds=10,
    )
    if not allowed:
        return

    await room_manager.broadcast_to_room_except(
        room_uid,
        {
            "type": "typing",
            "user_uid": str(user_uid),
            "active": active,
            "expires_in": 5,
        },
        exclude_user=user_uid,
    )


class TypingAwareWebSocket:
    """Duck-typed WebSocket proxy that consumes only PubChat typing frames.

    All canonical room frames continue through the existing room handler unchanged.
    The proxy deliberately stores no text, cursor position or draft content.
    """

    def __init__(
        self,
        websocket: WebSocket,
        room_uid: UUID,
        user_uid: UUID,
        db_session: AsyncSession,
    ) -> None:
        self._websocket = websocket
        self._room_uid = room_uid
        self._user_uid = user_uid
        self._db_session = db_session

    def __getattr__(self, name):
        return getattr(self._websocket, name)

    async def receive_json(self, *args, **kwargs):
        while True:
            data = await self._websocket.receive_json(*args, **kwargs)
            if not isinstance(data, dict) or data.get("type") != "typing":
                return data

            # The legacy room handler normally refreshes presence immediately after
            # receive_json. Typing frames are consumed here, so refresh it explicitly.
            await room_manager.touch_connection(self)
            await relay_typing(
                self._room_uid,
                self._user_uid,
                self._db_session,
                data.get("active"),
            )


@get_session
async def handle_websocket_connection(
    websocket: WebSocket,
    room_uid: UUID | str,
    user: dict,
    db_session: AsyncSession = None,
):
    """Run the existing room lifecycle with an ephemeral typing-frame interceptor."""
    normalized_room_uid = UUID(str(room_uid))
    user_uid = UUID(str(user["user_uid"]))
    proxy = TypingAwareWebSocket(
        websocket,
        normalized_room_uid,
        user_uid,
        db_session,
    )
    await _handle_websocket_connection(proxy, normalized_room_uid, user)
