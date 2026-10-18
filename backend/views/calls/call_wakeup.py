"""Best-effort, privacy-minimal call alert.

No SDP/ICE, message bodies or caller name are passed to FCM. The authenticated
client fetches its pending offer from the backend after it is opened.
"""
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from components.notification.native_push import FCMProvider, NativePushProviderError, _targets
from utils.logger import setup_logger

logger = setup_logger(__name__)


async def wake_android_recipient(db: AsyncSession, recipient_uid: UUID, call_uid: str) -> None:
    provider = FCMProvider()
    if not provider.configured:
        return
    targets = await _targets(db, recipient_uid)
    payload = {
        "type": "call",
        "call_uid": call_uid,
        "title": "Входящий звонок PubChat",
        "body": "Откройте PubChat, чтобы ответить.",
        "url": "/messenger",
        "tag": "pubchat-incoming-call",
    }
    for target in targets:
        if target.provider != "fcm" or target.platform != "android":
            continue
        try:
            await provider.send(target, payload)
        except NativePushProviderError as exc:
            logger.warning("Call wakeup delivery failed: %s", exc.failure_class)
        except Exception:
            logger.warning("Call wakeup delivery unavailable")
