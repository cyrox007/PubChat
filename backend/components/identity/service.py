import re
from datetime import datetime, timedelta
from hashlib import sha256
from uuid import UUID, uuid4

from fastapi import HTTPException, Request, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from components.device.model import UserDevice
from components.identity.model import (
    Account,
    AccountRole,
    Credential,
    IdentitySession,
    Persona,
    PlatformRole,
    PrivacySettings,
)
from components.identity.schemas import (
    PersonaCreateRequest, PersonaUpdateRequest, PrivacyUpdateRequest, RegisterRequest,
)
from components.user.model import User
from services.auth_service import generate_tokens
from settings import config
from utils.jwt import validate_refresh_token
from utils.password import hash_password, verify_password
from utils.user_agents import parse_user_agent

DEVICE_ID_HEADER = "X-PubChat-Device-ID"


def _token_hash(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def _client_metadata(request: Request) -> tuple[str, str, dict]:
    ip_address = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("User-Agent", "unknown")
    return ip_address, user_agent, parse_user_agent(user_agent)


def _client_device_uid(request: Request) -> UUID:
    raw = str(request.headers.get(DEVICE_ID_HEADER) or "").strip()
    try:
        return UUID(raw)
    except (ValueError, TypeError, AttributeError):
        # A device id is a grouping hint, not an authentication credential.
        # Invalid/missing values get a fresh server-generated id instead of
        # weakening the session boundary.
        return uuid4()


def _normalize_identifier(value: str) -> list[str]:
    normalized = value.strip().casefold()
    candidates = [normalized]
    phone = re.sub(r"[^0-9+]", "", value.strip())
    if phone and phone != normalized:
        candidates.append(phone)
    return list(dict.fromkeys(candidates))


async def _role_name(db: AsyncSession, account_uid: UUID) -> str:
    result = await db.execute(
        select(PlatformRole.name)
        .join(AccountRole, AccountRole.role_id == PlatformRole.id)
        .where(AccountRole.account_uid == account_uid)
        .order_by(PlatformRole.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none() or "user"


async def _primary_persona(db: AsyncSession, account_uid: UUID) -> Persona | None:
    result = await db.execute(
        select(Persona)
        .where(Persona.account_uid == account_uid, Persona.is_primary.is_(True))
        .order_by(Persona.created_at.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def selected_persona(
    db: AsyncSession, account_uid: UUID, session_uid: str | None = None
) -> Persona | None:
    # Tokens identify the Account, never a user-controlled Persona.
    if session_uid:
        try:
            sid = UUID(str(session_uid))
        except (ValueError, TypeError):
            sid = None
        if sid:
            result = await db.execute(
                select(IdentitySession.active_persona_uid).where(
                    IdentitySession.uid == sid,
                    IdentitySession.account_uid == account_uid,
                    IdentitySession.revoked_at.is_(None),
                    IdentitySession.expires_at > datetime.utcnow(),
                ).limit(1)
            )
            selected = result.scalar_one_or_none()
            if selected:
                persona = await db.get(Persona, selected)
                if persona and persona.account_uid == account_uid:
                    return persona
    return await _primary_persona(db, account_uid)


def persona_projection(persona: Persona) -> dict:
    return {
        "uid": str(persona.uid),
        "handle": persona.handle,
        "display_name": persona.display_name,
        "avatar": persona.avatar,
        "bio": persona.bio,
        "city": persona.city,
        "country": persona.country,
        "social_intent": persona.social_intent,
        "is_primary": persona.is_primary,
    }


async def list_account_personas(db: AsyncSession, account_uid: UUID, session_uid: str | None) -> dict:
    result = await db.execute(
        select(Persona).where(Persona.account_uid == account_uid)
        .order_by(Persona.is_primary.desc(), Persona.created_at.asc(), Persona.uid.asc())
    )
    personas = result.scalars().all()
    active = await selected_persona(db, account_uid, session_uid)
    return {
        "personas": [persona_projection(item) for item in personas],
        "active_persona_uid": str(active.uid) if active else None,
    }


async def create_account_persona(
    db: AsyncSession, account: Account, payload: PersonaCreateRequest,
) -> Persona:
    # Serialize concurrent creates under the same Account to enforce a cap.
    await db.execute(select(Account.uid).where(Account.uid == account.uid).with_for_update())
    count = await db.scalar(
        select(func.count(Persona.uid)).where(Persona.account_uid == account.uid)
    )
    if (count or 0) >= 3:
        raise HTTPException(status_code=409, detail={"error_type": "persona_limit_reached"})

    handle = payload.handle.strip()
    existing = await db.scalar(
        select(Persona.uid).where(func.lower(Persona.handle) == handle.casefold()).limit(1)
    )
    if existing:
        raise HTTPException(status_code=409, detail={"error_type": "handle_taken", "field": "handle"})

    persona = Persona(
        account_uid=account.uid, handle=handle,
        display_name=payload.display_name or handle,
        bio=payload.bio, social_intent=payload.social_intent,
        is_primary=False,
    )
    db.add(persona)
    try:
        await db.flush()
        # Secondary Personas must not silently enter discovery or accept unsolicited DM.
        db.add(PrivacySettings(
            persona_uid=persona.uid, profile_visibility="private", dm_policy="nobody",
        ))
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409, detail={"error_type": "handle_taken", "field": "handle"}
        ) from exc
    await db.refresh(persona)
    return persona


async def activate_account_persona(
    db: AsyncSession, account_uid: UUID, session_uid: str | None, persona_uid: UUID
) -> None:
    if not session_uid:
        raise HTTPException(status_code=409, detail={"error_type": "session_identity_required"})
    try:
        sid = UUID(str(session_uid))
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=401, detail={"error_type": "invalid_session"}) from exc

    result = await db.execute(
        select(IdentitySession).where(
            IdentitySession.uid == sid, IdentitySession.account_uid == account_uid,
            IdentitySession.revoked_at.is_(None),
            IdentitySession.expires_at > datetime.utcnow(),
        ).with_for_update().limit(1)
    )
    identity_session = result.scalar_one_or_none()
    if identity_session is None:
        raise HTTPException(status_code=401, detail={"error_type": "session_revoked"})
    persona = await db.get(Persona, persona_uid)
    if persona is None or persona.account_uid != account_uid:
        # Avoid disclosing another Account's Personas.
        raise HTTPException(status_code=404, detail={"error_type": "persona_not_found"})
    identity_session.active_persona_uid = None if persona.is_primary else persona.uid
    await db.commit()


async def _legacy_user_by_uid(db: AsyncSession, user_uid: UUID | None) -> User | None:
    if not user_uid:
        return None
    result = await db.execute(select(User).where(User.uid == user_uid).limit(1))
    return result.scalar_one_or_none()


async def build_identity_projection(
    db: AsyncSession, account: Account, session_uid: str | None = None
) -> dict:
    persona = await selected_persona(db, account.uid, session_uid)
    role = await _role_name(db, account.uid)
    privacy = await db.get(PrivacySettings, persona.uid) if persona else None

    persona_data = None
    if persona:
        persona_data = persona_projection(persona)

    privacy_data = None
    if privacy:
        privacy_data = {
            "profile_visibility": privacy.profile_visibility,
            "dm_policy": privacy.dm_policy,
            "show_last_seen": privacy.show_last_seen,
            "show_age": privacy.show_age,
            "share_birthday_with_friends": privacy.share_birthday_with_friends,
            "show_location": privacy.show_location,
        }

    compatibility_user = None
    if persona:
        compatibility_user = {
            "uid": str(account.uid),
            "username": persona.handle,
            "display_name": persona.display_name,
            "avatar": persona.avatar,
            "bio": persona.bio,
            "city": persona.city,
            "country": persona.country,
            "global_role": role,
            "trust_level": account.trust_level,
            "social_intent": persona.social_intent,
            "persona_uid": str(persona.uid),
        }

    return {
        "account": {
            "uid": str(account.uid),
            "status": account.status,
            "trust_level": account.trust_level,
            "created_at": account.created_at.isoformat() if account.created_at else None,
        },
        "persona": persona_data,
        "privacy": privacy_data,
        "role": role,
        "user": compatibility_user,
    }


async def build_public_profile(db: AsyncSession, account: Account, viewer_uid: str) -> dict:
    persona = await _primary_persona(db, account.uid)
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error_type": "persona_not_found"})

    privacy = await db.get(PrivacySettings, persona.uid)
    is_owner = str(account.uid) == str(viewer_uid)
    visibility = privacy.profile_visibility if privacy else "public"
    if visibility == "private" and not is_owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error_type": "profile_private"})

    show_location = is_owner or not privacy or privacy.show_location
    role = await _role_name(db, account.uid)
    return {
        "uid": str(account.uid),
        "persona_uid": str(persona.uid),
        "handle": persona.handle,
        "display_name": persona.display_name,
        "avatar": persona.avatar,
        "bio": persona.bio,
        "city": persona.city if show_location else None,
        "country": persona.country if show_location else None,
        "social_intent": persona.social_intent,
        "role": role if role != "user" else None,
        "is_self": is_owner,
        "contact_policy": privacy.dm_policy if privacy else "shared_spaces",
    }


async def _issue_session(db: AsyncSession, account: Account, request: Request) -> dict:
    session_uid = uuid4()
    device_uid = _client_device_uid(request)
    tokens = generate_tokens(
        str(account.uid),
        session_uid=str(session_uid),
        device_uid=str(device_uid),
    )
    ip_address, user_agent, device_info = _client_metadata(request)
    expires_at = datetime.utcnow() + timedelta(days=config.REFRESH_TOKEN_EXPIRE_DAYS)

    db.add(
        IdentitySession(
            uid=session_uid,
            account_uid=account.uid,
            device_uid=device_uid,
            refresh_token_hash=_token_hash(tokens["refresh"]),
            device_label=device_info.get("device") or device_info.get("device_type"),
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=expires_at,
        )
    )
    db.add(
        UserDevice(
            id=str(uuid4()),
            user_uid=account.uid,
            token=tokens["refresh"],
            ip_address=ip_address,
            user_agent=user_agent,
            device_info=device_info,
            expires_at=expires_at,
            is_active=True,
        )
    )
    return tokens


async def register_account(db: AsyncSession, payload: RegisterRequest, request: Request) -> tuple[Account, dict]:
    handle = payload.handle.strip()
    normalized_handle = handle.casefold()
    existing_handle = await db.execute(
        select(Persona.uid).where(func.lower(Persona.handle) == normalized_handle).limit(1)
    )
    if existing_handle.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error_type": "handle_taken", "field": "handle"})

    email = str(payload.email).strip().casefold() if payload.email else None
    if email:
        existing_email = await db.execute(
            select(Credential.uid).where(Credential.kind == "email", Credential.value_normalized == email).limit(1)
        )
        if existing_email.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"error_type": "email_taken", "field": "email"})

    account_uid = uuid4()
    password_hash = hash_password(payload.password)
    display_name = payload.display_name or handle

    legacy_user = User(
        uid=account_uid,
        username=handle,
        email=email,
        phone=None,
        hashed_password=password_hash,
        avatar="/static/default_male.webp",
        global_role="user",
        rating=0,
        is_active=True,
        is_verified=False,
        bio=payload.bio,
    )
    db.add(legacy_user)
    await db.flush()

    account = Account(uid=account_uid, legacy_user_uid=account_uid, status="active", trust_level="new")
    db.add(account)
    await db.flush()

    persona = Persona(
        account_uid=account_uid,
        handle=handle,
        display_name=display_name,
        avatar=legacy_user.avatar,
        bio=payload.bio,
        social_intent=payload.social_intent,
        is_primary=True,
    )
    db.add(persona)
    await db.flush()

    db.add(Credential(account_uid=account_uid, kind="password", secret_hash=password_hash, is_primary=True))
    if email:
        db.add(Credential(account_uid=account_uid, kind="email", value_normalized=email, is_primary=True))
    db.add(PrivacySettings(persona_uid=persona.uid))
    db.add(AccountRole(account_uid=account_uid, role_id=1))

    tokens = await _issue_session(db, account, request)
    await db.commit()
    await db.refresh(account)
    return account, tokens


async def authenticate_account(db: AsyncSession, identifier: str, password: str, request: Request) -> tuple[Account, dict]:
    candidates = _normalize_identifier(identifier)
    persona_result = await db.execute(
        select(Persona).where(func.lower(Persona.handle) == candidates[0]).limit(1)
    )
    persona = persona_result.scalar_one_or_none()
    account_uid = persona.account_uid if persona else None

    if account_uid is None:
        credential_result = await db.execute(
            select(Credential).where(
                Credential.kind.in_(["email", "phone"]),
                Credential.value_normalized.in_(candidates),
            ).limit(1)
        )
        identifier_credential = credential_result.scalar_one_or_none()
        account_uid = identifier_credential.account_uid if identifier_credential else None

    if account_uid is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"error_type": "invalid_credentials"})

    account = await db.get(Account, account_uid)
    if not account or account.status != "active" or account.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error_type": "account_unavailable"})

    password_result = await db.execute(
        select(Credential).where(Credential.account_uid == account.uid, Credential.kind == "password").limit(1)
    )
    password_credential = password_result.scalar_one_or_none()
    if not password_credential or not password_credential.secret_hash or not verify_password(password, password_credential.secret_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"error_type": "invalid_credentials"})

    tokens = await _issue_session(db, account, request)
    await db.commit()
    return account, tokens


async def rotate_session(db: AsyncSession, refresh_token: str, request: Request) -> tuple[Account, dict]:
    payload = validate_refresh_token(refresh_token)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"error_type": "invalid_refresh_token"})

    result = await db.execute(
        select(IdentitySession).where(
            IdentitySession.refresh_token_hash == _token_hash(refresh_token),
            IdentitySession.revoked_at.is_(None),
            IdentitySession.expires_at > datetime.utcnow(),
        ).with_for_update().limit(1)
    )
    identity_session = result.scalar_one_or_none()
    if not identity_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"error_type": "session_not_found"})

    account = await db.get(Account, identity_session.account_uid)
    if not account or account.status != "active" or str(account.uid) != payload.get("user_uid"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail={"error_type": "account_unavailable"})
    if payload.get("session_uid") and payload["session_uid"] != str(identity_session.uid):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"error_type": "session_mismatch"})

    tokens = generate_tokens(
        str(account.uid),
        session_uid=str(identity_session.uid),
        device_uid=str(identity_session.device_uid),
    )
    identity_session.refresh_token_hash = _token_hash(tokens["refresh"])
    identity_session.last_seen_at = datetime.utcnow()
    identity_session.expires_at = datetime.utcnow() + timedelta(days=config.REFRESH_TOKEN_EXPIRE_DAYS)

    legacy_result = await db.execute(
        select(UserDevice).where(UserDevice.token == refresh_token, UserDevice.is_active.is_(True)).limit(1)
    )
    legacy_device = legacy_result.scalar_one_or_none()
    if legacy_device:
        ip_address, user_agent, _ = _client_metadata(request)
        legacy_device.token = tokens["refresh"]
        legacy_device.ip_address = ip_address
        legacy_device.user_agent = user_agent
        legacy_device.expires_at = identity_session.expires_at

    await db.commit()
    return account, tokens


async def active_identity_session(
    db: AsyncSession,
    account_uid: UUID | str,
    session_uid: UUID | str,
) -> IdentitySession | None:
    try:
        account_id = UUID(str(account_uid))
        session_id = UUID(str(session_uid))
    except (ValueError, TypeError):
        return None
    result = await db.execute(
        select(IdentitySession).where(
            IdentitySession.uid == session_id,
            IdentitySession.account_uid == account_id,
            IdentitySession.revoked_at.is_(None),
            IdentitySession.expires_at > datetime.utcnow(),
        ).limit(1)
    )
    return result.scalar_one_or_none()


async def list_account_sessions(
    db: AsyncSession,
    account_uid: UUID | str,
    current_session_uid: UUID | str | None = None,
) -> list[dict]:
    account_id = UUID(str(account_uid))
    current = str(current_session_uid or "")
    result = await db.execute(
        select(IdentitySession).where(
            IdentitySession.account_uid == account_id,
            IdentitySession.revoked_at.is_(None),
            IdentitySession.expires_at > datetime.utcnow(),
        ).order_by(IdentitySession.last_seen_at.desc(), IdentitySession.created_at.desc())
    )
    groups: dict[str, dict] = {}
    for session in result.scalars().all():
        device_uid = str(session.device_uid)
        group = groups.setdefault(
            device_uid,
            {
                "device_uid": device_uid,
                "device_label": session.device_label or "Неизвестное устройство",
                "user_agent": session.user_agent,
                "last_seen_at": session.last_seen_at.isoformat() if session.last_seen_at else None,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "current": False,
                "sessions": [],
            },
        )
        is_current = str(session.uid) == current
        group["current"] = group["current"] or is_current
        if session.last_seen_at and (not group["last_seen_at"] or session.last_seen_at.isoformat() > group["last_seen_at"]):
            group["last_seen_at"] = session.last_seen_at.isoformat()
        group["sessions"].append(
            {
                "uid": str(session.uid),
                "current": is_current,
                "ip_address": session.ip_address,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "last_seen_at": session.last_seen_at.isoformat() if session.last_seen_at else None,
                "expires_at": session.expires_at.isoformat() if session.expires_at else None,
            }
        )
    return list(groups.values())


async def revoke_session_by_uid(
    db: AsyncSession,
    account_uid: UUID | str,
    session_uid: UUID | str,
) -> IdentitySession | None:
    session = await active_identity_session(db, account_uid, session_uid)
    if not session:
        return None
    session.revoked_at = datetime.utcnow()
    await db.commit()
    return session


async def revoke_device_sessions(
    db: AsyncSession,
    account_uid: UUID | str,
    device_uid: UUID | str,
) -> int:
    account_id = UUID(str(account_uid))
    device_id = UUID(str(device_uid))
    result = await db.execute(
        update(IdentitySession)
        .where(
            IdentitySession.account_uid == account_id,
            IdentitySession.device_uid == device_id,
            IdentitySession.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.utcnow())
    )
    await db.commit()
    return int(result.rowcount or 0)


async def revoke_other_sessions(
    db: AsyncSession,
    account_uid: UUID | str,
    current_session_uid: UUID | str,
) -> int:
    account_id = UUID(str(account_uid))
    current_id = UUID(str(current_session_uid))
    result = await db.execute(
        update(IdentitySession)
        .where(
            IdentitySession.account_uid == account_id,
            IdentitySession.uid != current_id,
            IdentitySession.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.utcnow())
    )
    await db.commit()
    return int(result.rowcount or 0)


async def revoke_session(db: AsyncSession, refresh_token: str | None) -> IdentitySession | None:
    if not refresh_token:
        return None

    result = await db.execute(
        select(IdentitySession).where(
            IdentitySession.refresh_token_hash == _token_hash(refresh_token),
            IdentitySession.revoked_at.is_(None),
        ).limit(1)
    )
    identity_session = result.scalar_one_or_none()
    if identity_session:
        identity_session.revoked_at = datetime.utcnow()

    legacy_result = await db.execute(
        select(UserDevice).where(UserDevice.token == refresh_token, UserDevice.is_active.is_(True)).limit(1)
    )
    legacy_device = legacy_result.scalar_one_or_none()
    if legacy_device:
        legacy_device.is_active = False

    await db.commit()
    return identity_session


async def get_account_by_uid(db: AsyncSession, account_uid: str) -> Account:
    try:
        uid = UUID(str(account_uid))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail={"error_type": "invalid_subject"}) from exc

    account = await db.get(Account, uid)
    if not account or account.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error_type": "account_not_found"})
    return account


async def update_primary_persona(
    db: AsyncSession, account: Account, payload: PersonaUpdateRequest,
    session_uid: str | None = None,
) -> dict:
    persona = await selected_persona(db, account.uid, session_uid)
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error_type": "persona_not_found"})

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(persona, field, value)

    legacy_user = await _legacy_user_by_uid(db, account.legacy_user_uid)
    if legacy_user and persona.is_primary:
        for field in ("avatar", "bio", "city", "country"):
            if field in updates:
                setattr(legacy_user, field, updates[field])

    await db.commit()
    await db.refresh(persona)
    return await build_identity_projection(db, account, session_uid)


async def update_privacy(
    db: AsyncSession, account: Account, payload: PrivacyUpdateRequest,
    session_uid: str | None = None,
) -> dict:
    persona = await selected_persona(db, account.uid, session_uid)
    if not persona:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"error_type": "persona_not_found"})
    if not persona.is_primary:
        # Account-level messaging policy still reads the canonical Persona.
        # Do not let the secondary profile pretend to change this policy.
        raise HTTPException(status_code=409, detail={"error_type": "secondary_privacy_not_supported"})

    privacy = await db.get(PrivacySettings, persona.uid)
    if not privacy:
        privacy = PrivacySettings(persona_uid=persona.uid)
        db.add(privacy)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(privacy, field, value)

    await db.commit()
    return await build_identity_projection(db, account, session_uid)
