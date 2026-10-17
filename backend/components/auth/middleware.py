from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy import select

from components.identity.model import IdentitySession
from components.moderation.account_access import assert_http_account_access
from database import Database
from utils.jwt import validate_access_token
from utils.logger import setup_logger

logger = setup_logger(__name__)


async def auth_middle(request: Request):
    token = request.headers.get("authorization")
    if not token:
        logger.warning("Отсутствующий токен в HTTP-запросе")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "bad", "error_type": "missing_token"},
        )

    user_data = validate_access_token(token)
    if not user_data:
        logger.warning("Недопустимый токен в HTTP-запросе")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "bad", "error_type": "invalid_token"},
        )

    request.state.user = user_data
    request.state.user_uid = user_data["user_uid"]
    request.state.session_uid = user_data.get("session_uid")
    request.state.device_uid = user_data.get("device_uid")

    session = await Database.get_session()
    try:
        # Identity v2 access tokens are session-bound. This makes per-session
        # revocation effective immediately instead of waiting for JWT expiry.
        # Legacy tokens without sid remain accepted during compatibility sunset.
        if user_data.get("session_uid"):
            try:
                session_uid = UUID(str(user_data["session_uid"]))
                account_uid = UUID(str(user_data["user_uid"]))
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={"status": "bad", "error_type": "invalid_session"},
                ) from exc
            result = await session.execute(
                select(IdentitySession.uid).where(
                    IdentitySession.uid == session_uid,
                    IdentitySession.account_uid == account_uid,
                    IdentitySession.revoked_at.is_(None),
                    IdentitySession.expires_at > datetime.utcnow(),
                ).limit(1)
            )
            if result.scalar_one_or_none() is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={"status": "bad", "error_type": "session_revoked"},
                )

        await assert_http_account_access(
            session,
            request,
            user_data["user_uid"],
        )
    finally:
        await session.close()

    logger.info("HTTP-аутентификация успешна для пользователя %s", user_data["user_uid"])
    return user_data


async def authorize_user(current_user, target_user_uid, required_role=None):
    """
    Legacy authorization helper kept for compatibility during the revival migration.

    Role checks must not rely on JWT claims. Use server-side permission dependencies
    that read the current role from the database.
    """
    current_uid = current_user.get("user_uid")
    if current_uid == str(target_user_uid):
        return True

    if required_role:
        logger.warning(
            "Отклонена legacy-проверка роли %s для пользователя %s",
            required_role,
            current_uid,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"status": "bad", "error_type": "insufficient_permissions"},
        )

    return False
