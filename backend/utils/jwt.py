import jwt
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from settings import config
from utils.logger import setup_logger

logger = setup_logger(__name__)


def _security_ready():
    config.ensure_security_settings()


def _identity_claims(payload: Dict[str, Any]) -> Dict[str, str]:
    claims: Dict[str, str] = {}
    session_uid = payload.get("session_uid")
    device_uid = payload.get("device_uid")
    if session_uid:
        claims["sid"] = str(session_uid)
    if device_uid:
        claims["did"] = str(device_uid)
    return claims


def create_access_token(payload: Dict[str, Any]) -> str:
    """Generate a signed short-lived access token."""
    _security_ready()
    user_uid = str(payload.get("user_uid") or "")
    if not user_uid:
        raise ValueError("user_uid is required")

    return jwt.encode(
        {
            "sub": user_uid,
            "iat": datetime.now(timezone.utc),
            "jti": str(uuid4()),
            "exp": datetime.now(timezone.utc)
            + timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES),
            "type": "access",
            **_identity_claims(payload),
        },
        config.JWT_ACCESS_SECRET_KEY,
        algorithm=config.JWT_ALGORITHM,
    )


def create_refresh_token(payload: Dict[str, Any]) -> str:
    """Generate a signed refresh token."""
    _security_ready()
    user_uid = str(payload.get("user_uid") or "")
    if not user_uid:
        raise ValueError("user_uid is required")

    return jwt.encode(
        {
            "sub": user_uid,
            "iat": datetime.now(timezone.utc),
            "jti": str(uuid4()),
            "exp": datetime.now(timezone.utc)
            + timedelta(days=config.REFRESH_TOKEN_EXPIRE_DAYS),
            "type": "refresh",
            **_identity_claims(payload),
        },
        config.JWT_REFRESH_SECRET_KEY,
        algorithm=config.JWT_ALGORITHM,
    )


def _validated_identity(payload: Dict[str, Any], expected_type: str) -> Optional[Dict[str, Any]]:
    if payload.get("type") != expected_type:
        logger.warning("Попытка использовать токен неверного типа")
        return None

    sub = payload.get("sub")
    if not isinstance(sub, str):
        logger.warning("Subject must be a string")
        return None

    result: Dict[str, Any] = {"user_uid": sub}
    session_uid = payload.get("sid")
    device_uid = payload.get("did")
    if session_uid is not None:
        if not isinstance(session_uid, str):
            return None
        result["session_uid"] = session_uid
    if device_uid is not None:
        if not isinstance(device_uid, str):
            return None
        result["device_uid"] = device_uid
    return result


def validate_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Validate an access token without ever writing token material to logs."""
    _security_ready()
    try:
        if not token:
            logger.warning("Получен пустой access-токен")
            return None

        if token.startswith("Bearer "):
            token = token.split(" ", 1)[1]

        payload = jwt.decode(
            token,
            config.JWT_ACCESS_SECRET_KEY,
            algorithms=[config.JWT_ALGORITHM],
            options={"verify_exp": True},
        )
        return _validated_identity(payload, "access")

    except jwt.ExpiredSignatureError:
        logger.info("Истек срок действия access-токена")
        return None
    except jwt.InvalidTokenError as exc:
        logger.warning("Невалидный access-токен: %s", exc)
        return None


def validate_refresh_token(token: str) -> Optional[Dict[str, Any]]:
    """Validate a refresh token without ever writing token material to logs."""
    _security_ready()
    try:
        if not token:
            logger.warning("Получен пустой refresh-токен")
            return None

        payload = jwt.decode(
            token,
            config.JWT_REFRESH_SECRET_KEY,
            algorithms=[config.JWT_ALGORITHM],
            options={"verify_exp": True},
        )
        return _validated_identity(payload, "refresh")

    except jwt.ExpiredSignatureError:
        logger.info("Истек срок действия refresh-токена")
        return None
    except jwt.InvalidTokenError as exc:
        logger.warning("Невалидный refresh-токен: %s", exc)
        return None
