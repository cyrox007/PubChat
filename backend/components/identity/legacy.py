from datetime import datetime, timedelta
from hashlib import sha256
from uuid import UUID, uuid4

from fastapi import HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from components.device.model import UserDevice
from components.identity.model import Account, IdentitySession
from components.identity.service import DEVICE_ID_HEADER, rotate_session
from services.auth_service import generate_tokens
from settings import config
from utils.jwt import validate_refresh_token
from utils.user_agents import parse_user_agent


def _hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def _legacy_device_uid(request: Request) -> UUID:
    try:
        return UUID(str(request.headers.get(DEVICE_ID_HEADER) or ""))
    except (ValueError, TypeError, AttributeError):
        return uuid4()


async def rotate_session_with_legacy_fallback(
    db: AsyncSession,
    refresh_token: str,
    request: Request,
) -> tuple[Account, dict]:
    try:
        return await rotate_session(db, refresh_token, request)
    except HTTPException as exc:
        error_type = exc.detail.get("error_type") if isinstance(exc.detail, dict) else None
        if exc.status_code != status.HTTP_401_UNAUTHORIZED or error_type != "session_not_found":
            raise

    payload = validate_refresh_token(refresh_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_type": "invalid_refresh_token"},
        )

    # Only genuinely legacy refresh tokens may use the compatibility bridge.
    # A modern token with sid that lost its IdentitySession was revoked/expired;
    # allowing it to fall back through the legacy UserDevice row would resurrect
    # a deliberately terminated session.
    if payload.get("session_uid"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_type": "session_not_found"},
        )

    legacy_result = await db.execute(
        select(UserDevice).where(
            UserDevice.token == refresh_token,
            UserDevice.is_active.is_(True),
            UserDevice.expires_at > datetime.utcnow(),
        ).with_for_update().limit(1)
    )
    legacy_device = legacy_result.scalar_one_or_none()
    if not legacy_device:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_type": "session_not_found"},
        )

    try:
        account_uid = UUID(payload["user_uid"])
    except (ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_type": "invalid_subject"},
        ) from exc

    account = await db.get(Account, account_uid)
    if not account or account.status != "active" or account.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error_type": "account_unavailable"},
        )

    session_uid = uuid4()
    device_uid = _legacy_device_uid(request)
    tokens = generate_tokens(
        str(account.uid),
        session_uid=str(session_uid),
        device_uid=str(device_uid),
    )
    expires_at = datetime.utcnow() + timedelta(days=config.REFRESH_TOKEN_EXPIRE_DAYS)
    user_agent = request.headers.get("User-Agent", "unknown")
    device_info = parse_user_agent(user_agent)
    ip_address = request.client.host if request.client else "unknown"

    db.add(
        IdentitySession(
            uid=session_uid,
            account_uid=account.uid,
            device_uid=device_uid,
            refresh_token_hash=_hash_token(tokens["refresh"]),
            device_label=device_info.get("device") or device_info.get("device_type"),
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=expires_at,
        )
    )
    legacy_device.token = tokens["refresh"]
    legacy_device.expires_at = expires_at
    legacy_device.user_agent = user_agent
    legacy_device.ip_address = ip_address
    legacy_device.device_info = device_info

    await db.commit()
    return account, tokens
