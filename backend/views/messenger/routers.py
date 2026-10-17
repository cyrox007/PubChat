from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from components.auth.middleware import auth_middle
from components.message.encryption_policy import conversation_policy, set_conversation_mode
from database import Database
from views.messenger import handlers
from views.messenger.ws_handlers import _dm_allowed


class ConversationEncryptionUpdate(BaseModel):
    mode: str


def _account_uid(current_user: dict) -> UUID:
    try:
        return UUID(str(current_user["user_uid"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"error_type": "invalid_subject"}) from exc


def install(app: FastAPI):
    router = APIRouter(prefix='/messenger')

    router.add_api_route(
        '/dialogs',
        methods=['GET'],
        endpoint=handlers.get_dialogs,
        dependencies=[Depends(auth_middle)]
    )

    @router.get('/conversations/{peer_uid}/encryption')
    async def get_conversation_encryption(
        peer_uid: UUID,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        account_uid = _account_uid(current_user)
        if not await _dm_allowed(db, account_uid, peer_uid):
            raise HTTPException(status_code=404, detail={"error_type": "conversation_not_available"})
        return {"status": "ok", "encryption": await conversation_policy(db, account_uid, peer_uid)}

    @router.put('/conversations/{peer_uid}/encryption')
    async def update_conversation_encryption(
        peer_uid: UUID,
        payload: ConversationEncryptionUpdate,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        account_uid = _account_uid(current_user)
        if not await _dm_allowed(db, account_uid, peer_uid):
            raise HTTPException(status_code=404, detail={"error_type": "conversation_not_available"})
        encryption = await set_conversation_mode(
            db,
            account_uid=account_uid,
            peer_uid=peer_uid,
            mode=payload.mode,
        )
        return {"status": "ok", "encryption": encryption}

    app.include_router(router)
