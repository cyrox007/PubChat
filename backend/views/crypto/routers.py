from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from components.auth.middleware import auth_middle
from components.device.crypto_schemas import (
    DeviceRegistrationRequest,
    OneTimePreKeyBatchRequest,
    SignedPreKeyRotationRequest,
)
from components.device.crypto_service import (
    add_one_time_prekeys,
    claim_prekey_bundle,
    list_own_devices,
    register_device,
    revoke_device,
    rotate_signed_prekey,
)
from database import Database
from views.messenger.ws_handlers import _dm_allowed


def _account_uid(current_user: dict) -> UUID:
    try:
        return UUID(str(current_user["user_uid"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_type": "invalid_subject"},
        ) from exc


def install(app: FastAPI) -> None:
    router = APIRouter(prefix="/crypto/v1", tags=["crypto-v1"])

    @router.post("/devices", status_code=status.HTTP_201_CREATED)
    async def register_crypto_device(
        payload: DeviceRegistrationRequest,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        device = await register_device(
            db,
            account_uid=_account_uid(current_user),
            payload=payload,
        )
        return {"status": "ok", "device": device}

    @router.get("/devices")
    async def own_crypto_devices(
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        devices = await list_own_devices(db, account_uid=_account_uid(current_user))
        return {"status": "ok", "devices": devices}

    @router.put("/devices/{device_uid}/signed-prekey")
    async def update_signed_prekey(
        device_uid: UUID,
        payload: SignedPreKeyRotationRequest,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        device = await rotate_signed_prekey(
            db,
            account_uid=_account_uid(current_user),
            device_uid=device_uid,
            signed_prekey=payload.signed_prekey,
        )
        return {"status": "ok", "device": device}

    @router.post("/devices/{device_uid}/one-time-prekeys")
    async def replenish_one_time_prekeys(
        device_uid: UUID,
        payload: OneTimePreKeyBatchRequest,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        result = await add_one_time_prekeys(
            db,
            account_uid=_account_uid(current_user),
            device_uid=device_uid,
            prekeys=payload.one_time_prekeys,
        )
        return {"status": "ok", **result}

    @router.delete("/devices/{device_uid}")
    async def revoke_crypto_device(
        device_uid: UUID,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        result = await revoke_device(
            db,
            account_uid=_account_uid(current_user),
            device_uid=device_uid,
        )
        return {"status": "ok", **result}

    @router.get("/accounts/{target_account_uid}/prekey-bundle")
    async def account_prekey_bundle(
        target_account_uid: UUID,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        requester_uid = _account_uid(current_user)
        if not await _dm_allowed(db, requester_uid, target_account_uid):
            # Do not leak whether a target has devices/keys when the caller is
            # not currently eligible to initiate a direct conversation.
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_type": "prekey_bundle_not_available"},
            )
        bundle = await claim_prekey_bundle(db, target_account_uid=target_account_uid)
        return {"status": "ok", "bundle": bundle}

    app.include_router(router)
