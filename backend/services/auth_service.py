from fastapi import HTTPException

from utils.logger import setup_logger
from components.user.model import User
from utils.jwt import create_access_token, create_refresh_token
from utils.password import verify_password

logger = setup_logger(__name__)

""" def authenticate_user(db_session, identifier: str, password: str) -> User:
    user = User.get_user_by_credentials(db_session, identifier)
    if not user or not verify_password(password, user.hashed_password):
        logger.warning(f"Неверные учетные данные для пользователя: {identifier}")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return user """


def generate_tokens(
    user_uid: str,
    *,
    session_uid: str | None = None,
    device_uid: str | None = None,
) -> dict:
    payload = {
        "user_uid": user_uid,
        "session_uid": session_uid,
        "device_uid": device_uid,
    }
    access_token = create_access_token(payload)
    refresh_token = create_refresh_token(payload)
    return {"access": access_token, "refresh": refresh_token}
