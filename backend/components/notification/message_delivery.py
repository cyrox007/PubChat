from __future__ import annotations

from typing import Mapping
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from components.notification.model import MessageNotificationPreference
from components.notification.schemas import MessageNotificationPreferenceUpdateRequest
from components.space.service import _get_account


SURFACE_MESSENGER = "messenger"
SURFACE_SPACE = "space"
SUPPORTED_MESSAGE_SURFACES = {SURFACE_MESSENGER, SURFACE_SPACE}

DEFAULT_MESSAGE_NOTIFICATION_PREFERENCES = {
    "messenger_in_app": True,
    "space_in_app": True,
    "messenger_sound": True,
    "space_sound": True,
    "email_unread_dm_nudge": False,
    "web_push_messenger": False,
    "web_push_space": False,
    "native_push_messenger": False,
    "native_push_space": False,
    "friend_birthday_reminders": False,
}


def message_notification_preference_projection(
    item: MessageNotificationPreference | None,
) -> dict:
    if item is None:
        return dict(DEFAULT_MESSAGE_NOTIFICATION_PREFERENCES)
    return {
        "messenger_in_app": bool(item.messenger_in_app),
        "space_in_app": bool(item.space_in_app),
        "messenger_sound": bool(item.messenger_sound),
        "space_sound": bool(item.space_sound),
        "email_unread_dm_nudge": bool(item.email_unread_dm_nudge),
        "web_push_messenger": bool(item.web_push_messenger),
        "web_push_space": bool(item.web_push_space),
        "native_push_messenger": bool(item.native_push_messenger),
        "native_push_space": bool(item.native_push_space),
        "friend_birthday_reminders": bool(item.friend_birthday_reminders),
    }


async def get_message_notification_preferences(
    db: AsyncSession,
    viewer_uid: UUID | str,
) -> dict:
    account = await _get_account(db, viewer_uid)
    item = await db.get(MessageNotificationPreference, account.uid)
    return message_notification_preference_projection(item)


async def update_message_notification_preferences(
    db: AsyncSession,
    viewer_uid: UUID | str,
    payload: MessageNotificationPreferenceUpdateRequest,
) -> dict:
    account = await _get_account(db, viewer_uid)
    item = await db.get(MessageNotificationPreference, account.uid)
    if item is None:
        item = MessageNotificationPreference(
            account_uid=account.uid,
            **DEFAULT_MESSAGE_NOTIFICATION_PREFERENCES,
        )
        db.add(item)

    updates = payload.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in updates.items():
        setattr(item, field, bool(value))

    await db.commit()
    await db.refresh(item)
    return message_notification_preference_projection(item)


def message_delivery_policy(
    surface: str,
    *,
    online: bool,
    active_context: bool,
    preferences: Mapping[str, bool] | None = None,
) -> dict:
    """Return alert/delivery hints without changing message authorization."""

    if surface not in SUPPORTED_MESSAGE_SURFACES:
        raise ValueError(f"Unsupported message notification surface: {surface}")

    prefs = dict(DEFAULT_MESSAGE_NOTIFICATION_PREFERENCES)
    if preferences:
        prefs.update({key: bool(value) for key, value in preferences.items() if key in prefs})

    if surface == SURFACE_MESSENGER:
        in_app_enabled = prefs["messenger_in_app"]
        sound_enabled = prefs["messenger_sound"]
        web_push_enabled = prefs["web_push_messenger"]
        native_push_enabled = prefs["native_push_messenger"]
    else:
        in_app_enabled = prefs["space_in_app"]
        sound_enabled = prefs["space_sound"]
        web_push_enabled = prefs["web_push_space"]
        native_push_enabled = prefs["native_push_space"]

    notify_in_app = bool(online and in_app_enabled and not active_context)
    play_sound = bool(notify_in_app and sound_enabled)

    external_eligible = bool(
        surface == SURFACE_MESSENGER
        and not online
        and (
            prefs["email_unread_dm_nudge"]
            or web_push_enabled
            or native_push_enabled
        )
    )

    return {
        "surface": surface,
        "online": bool(online),
        "active_context": bool(active_context),
        "notify_in_app": notify_in_app,
        "play_sound": play_sound,
        "email_nudge_eligible": bool(
            surface == SURFACE_MESSENGER
            and not online
            and prefs["email_unread_dm_nudge"]
        ),
        "web_push_eligible": bool(
            surface == SURFACE_MESSENGER
            and not online
            and web_push_enabled
        ),
        "native_push_eligible": bool(
            surface == SURFACE_MESSENGER
            and not online
            and native_push_enabled
        ),
        "external_eligible": external_eligible,
    }
