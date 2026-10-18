from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


ReminderLeadMinutes = Literal[15, 60, 1440]
NativePushPlatform = Literal["android", "ios"]
NativePushProvider = Literal["fcm", "apns"]


class ActivityReminderUpdateRequest(BaseModel):
    lead_minutes: ReminderLeadMinutes = 60


class MessageNotificationPreferenceUpdateRequest(BaseModel):
    messenger_in_app: bool | None = None
    space_in_app: bool | None = None
    messenger_sound: bool | None = None
    space_sound: bool | None = None
    email_unread_dm_nudge: bool | None = None
    web_push_messenger: bool | None = None
    web_push_space: bool | None = None
    native_push_messenger: bool | None = None
    native_push_space: bool | None = None
    friend_birthday_reminders: bool | None = None


class WebPushKeys(BaseModel):
    p256dh: str = Field(min_length=16, max_length=256)
    auth: str = Field(min_length=8, max_length=128)


class WebPushSubscriptionUpsertRequest(BaseModel):
    endpoint: str = Field(min_length=16, max_length=4096)
    keys: WebPushKeys


class WebPushSubscriptionRemoveRequest(BaseModel):
    endpoint: str = Field(min_length=16, max_length=4096)


class NativePushDeviceUpsertRequest(BaseModel):
    installation_uid: UUID
    platform: NativePushPlatform
    provider: NativePushProvider
    token: str = Field(min_length=16, max_length=4096)
    device_label: str | None = Field(default=None, max_length=120)
    app_version: str | None = Field(default=None, max_length=40)


class NativePushDeviceRemoveRequest(BaseModel):
    installation_uid: UUID
