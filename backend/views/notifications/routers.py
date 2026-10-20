from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from components.auth.middleware import auth_middle
from components.engagement.occurrence_service import (
    list_activity_occurrences,
    sync_activity_occurrences,
)
from components.notification.message_delivery import (
    get_message_notification_preferences,
    update_message_notification_preferences,
)
from components.notification.schemas import (
    ActivityReminderUpdateRequest,
    MessageNotificationPreferenceUpdateRequest,
    WebPushSubscriptionRemoveRequest,
    WebPushSubscriptionUpsertRequest,
    NativePushDeviceUpsertRequest,
    NativePushDeviceRemoveRequest,
)
from components.notification.birthday import sync_friend_birthdays
from components.notification.service import (
    delete_activity_reminder,
    list_notifications,
    list_space_reminders,
    mark_all_notifications_read,
    mark_notification_read,
    set_activity_reminder,
    sync_activity_reminders,
    unread_notification_count,
)
from components.notification.native_push import (
    upsert_native_push_device,
    list_native_push_devices,
    revoke_native_push_device,
    fcm_configured,
    apns_configured,
)
from components.notification.web_push import (
    remove_web_push_subscription,
    upsert_web_push_subscription,
    web_push_subscription_count,
)
from components.space.service import _get_account
from database import Database
from settings import config


def install(app: FastAPI) -> None:
    occurrences = APIRouter(prefix="/activity-occurrences/v1", tags=["activity-occurrences-v1"])
    notifications = APIRouter(prefix="/notifications/v1", tags=["notifications-v1"])

    @occurrences.get("/activities/{activity_uid}")
    async def activity_occurrence_list(
        activity_uid: UUID,
        limit: int = Query(default=20, ge=1, le=100),
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        items = await list_activity_occurrences(
            db,
            activity_uid,
            current_user["user_uid"],
            limit=limit,
        )
        return {"status": "ok", "occurrences": items}

    @occurrences.post("/activities/{activity_uid}/sync")
    async def activity_occurrence_sync(
        activity_uid: UUID,
        limit: int = Query(default=20, ge=1, le=100),
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        items = await sync_activity_occurrences(
            db,
            activity_uid,
            current_user["user_uid"],
            limit=limit,
        )
        return {"status": "ok", "occurrences": items}

    @notifications.post("/sync")
    async def sync_notifications(
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        await sync_activity_reminders(db, current_user["user_uid"])
        await sync_friend_birthdays(db, current_user["user_uid"])
        unread = await unread_notification_count(db, current_user["user_uid"])
        return {"status": "ok", "unread": unread}

    @notifications.get("/unread-count")
    async def notification_unread_count(
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        unread = await unread_notification_count(db, current_user["user_uid"])
        return {"status": "ok", "unread": unread}

    @notifications.get("/message-preferences")
    async def message_notification_preferences(
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        preferences = await get_message_notification_preferences(
            db,
            current_user["user_uid"],
        )
        return {"status": "ok", "preferences": preferences}

    @notifications.patch("/message-preferences")
    async def patch_message_notification_preferences(
        payload: MessageNotificationPreferenceUpdateRequest,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        preferences = await update_message_notification_preferences(
            db,
            current_user["user_uid"],
            payload,
        )
        return {"status": "ok", "preferences": preferences}

    @notifications.get("/native-push/config")
    async def native_push_config(current_user: dict = Depends(auth_middle)):
        _ = current_user
        return {"status": "ok", "fcm_enabled": fcm_configured(), "apns_enabled": apns_configured()}

    @notifications.get("/native-push/devices")
    async def native_push_devices(
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        account = await _get_account(db, current_user["user_uid"])
        return {"status": "ok", "devices": await list_native_push_devices(db, account.uid)}

    @notifications.post("/native-push/devices", status_code=status.HTTP_201_CREATED)
    async def native_push_register(
        payload: NativePushDeviceUpsertRequest,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        account = await _get_account(db, current_user["user_uid"])
        try:
            item = await upsert_native_push_device(db, account.uid, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail={"error_type": str(exc)}) from exc
        return {"status": "ok", "device": item}

    @notifications.post("/native-push/devices/remove")
    async def native_push_remove(
        payload: NativePushDeviceRemoveRequest,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        account = await _get_account(db, current_user["user_uid"])
        removed = await revoke_native_push_device(db, account.uid, payload.installation_uid)
        return {"status": "ok", "removed": removed}

    @notifications.get("/web-push/config")
    async def web_push_config(
        current_user: dict = Depends(auth_middle),
    ):
        _ = current_user
        return {
            "status": "ok",
            "enabled": config.web_push_configured(),
            "public_key": config.WEB_PUSH_VAPID_PUBLIC_KEY if config.web_push_configured() else None,
        }

    @notifications.get("/web-push/subscriptions/status")
    async def web_push_status(
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        account = await _get_account(db, current_user["user_uid"])
        count = await web_push_subscription_count(db, account.uid)
        return {"status": "ok", "registered_devices": count}

    @notifications.post("/web-push/subscriptions", status_code=status.HTTP_201_CREATED)
    async def register_web_push_subscription(
        payload: WebPushSubscriptionUpsertRequest,
        request: Request,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        if not config.web_push_configured():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={"error_type": "web_push_not_configured"},
            )
        account = await _get_account(db, current_user["user_uid"])
        try:
            item = await upsert_web_push_subscription(
                db,
                account.uid,
                payload,
                user_agent=request.headers.get("user-agent"),
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_type": str(exc)},
            ) from exc
        return {"status": "ok", "subscription": item}

    @notifications.post("/web-push/subscriptions/remove")
    async def unregister_web_push_subscription(
        payload: WebPushSubscriptionRemoveRequest,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        account = await _get_account(db, current_user["user_uid"])
        removed = await remove_web_push_subscription(db, account.uid, payload.endpoint)
        return {"status": "ok", "removed": removed}

    @notifications.get("")
    async def notification_list(
        limit: int = Query(default=50, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        items, total, unread = await list_notifications(
            db,
            current_user["user_uid"],
            limit=limit,
            offset=offset,
        )
        return {
            "status": "ok",
            "notifications": items,
            "pagination": {
                "limit": limit,
                "offset": offset,
                "count": len(items),
                "total": total,
            },
            "unread": unread,
        }

    @notifications.get("/spaces/{space_uid}/reminders")
    async def space_reminder_list(
        space_uid: UUID,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        items = await list_space_reminders(db, space_uid, current_user["user_uid"])
        return {"status": "ok", "reminders": items}

    @notifications.put("/activities/{activity_uid}/reminder")
    async def put_activity_reminder(
        activity_uid: UUID,
        payload: ActivityReminderUpdateRequest,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        item = await set_activity_reminder(
            db,
            activity_uid,
            current_user["user_uid"],
            payload,
        )
        return {"status": "ok", "reminder": item}

    @notifications.delete("/activities/{activity_uid}/reminder", status_code=status.HTTP_204_NO_CONTENT)
    async def remove_activity_reminder(
        activity_uid: UUID,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        await delete_activity_reminder(db, activity_uid, current_user["user_uid"])

    @notifications.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
    async def read_all_notifications(
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        await mark_all_notifications_read(db, current_user["user_uid"])

    @notifications.patch("/{notification_uid}/read")
    async def read_notification(
        notification_uid: UUID,
        current_user: dict = Depends(auth_middle),
        db: AsyncSession = Depends(Database.session_generator),
    ):
        item = await mark_notification_read(
            db,
            notification_uid,
            current_user["user_uid"],
        )
        return {"status": "ok", "notification": item}

    app.include_router(occurrences)
    app.include_router(notifications)
