from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from components.auth.middleware import auth_middle
from components.notification.native_push import (
    list_native_push_devices,
    revoke_native_push_device,
    upsert_native_push_device,
)
from components.notification.native_push_config import validate_fcm_configuration
from components.notification.schemas import NativePushDeviceRemoveRequest, NativePushDeviceUpsertRequest
from components.space.service import _get_account
from database import Database


def install(app: FastAPI) -> None:
    router = APIRouter(prefix="/notifications/v1/native-push", tags=["native-push-v1"])

    @router.get("/config")
    async def native_push_config(current_user: dict = Depends(auth_middle)):
        _ = current_user
        fcm = validate_fcm_configuration()
        return {
            "status": "ok",
            "release_scope": "android-first-1.0",
            "android": {
                "provider": "fcm",
                "supported": True,
                "enabled": bool(fcm["valid"]),
                "transport": fcm["transport"],
                "configuration_errors": fcm["errors"],
            },
            "ios": {
                "provider": "apns",
                "supported": False,
                "enabled": False,
                "release_status": "post-1.0",
            },
            "privacy": {"message_content_in_push": False},
        }

    @router.get("/devices")
    async def native_push_devices(
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        account = await _get_account(db, current_user["user_uid"])
        devices = await list_native_push_devices(db, account.uid)
        return {"status": "ok", "devices": devices}

    @router.post("/devices", status_code=status.HTTP_201_CREATED)
    async def register_native_push_device(
        payload: NativePushDeviceUpsertRequest,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        account = await _get_account(db, current_user["user_uid"])
        try:
            device = await upsert_native_push_device(db, account.uid, payload)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_type": str(exc)},
            ) from exc
        return {"status": "ok", "device": device}

    @router.post("/devices/remove")
    async def unregister_native_push_device(
        payload: NativePushDeviceRemoveRequest,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        account = await _get_account(db, current_user["user_uid"])
        removed = await revoke_native_push_device(db, account.uid, payload.installation_uid)
        return {"status": "ok", "removed": removed}

    app.include_router(router)
