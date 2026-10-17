from __future__ import annotations

import os
import re
import time

import jwt


FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
FCM_TOKEN_URL = "https://oauth2.googleapis.com/token"
_PROJECT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$")


def fcm_project_id() -> str:
    return os.getenv("FCM_PROJECT_ID", "").strip()


def fcm_service_account_email() -> str:
    return os.getenv("FCM_SERVICE_ACCOUNT_EMAIL", "").strip()


def fcm_private_key() -> str:
    return os.getenv("FCM_SERVICE_ACCOUNT_PRIVATE_KEY", "").replace("\\n", "\n").strip()


def validate_fcm_configuration() -> dict:
    """Validate direct-FCM credentials locally without contacting Google.

    The result is safe to expose through an authenticated config endpoint: it
    contains readiness/error classes only and never returns credential values.
    """

    project_id = fcm_project_id()
    email = fcm_service_account_email()
    private_key = fcm_private_key()
    configured = bool(project_id and email and private_key)
    errors: list[str] = []

    if not project_id:
        errors.append("fcm_project_id_missing")
    elif not _PROJECT_ID_RE.fullmatch(project_id):
        errors.append("fcm_project_id_invalid")

    if not email:
        errors.append("fcm_service_account_email_missing")
    elif "@" not in email or len(email) > 320:
        errors.append("fcm_service_account_email_invalid")

    if not private_key:
        errors.append("fcm_private_key_missing")
    else:
        now = int(time.time())
        try:
            jwt.encode(
                {
                    "iss": email or "preflight@example.invalid",
                    "scope": FCM_SCOPE,
                    "aud": FCM_TOKEN_URL,
                    "iat": now,
                    "exp": now + 300,
                },
                private_key,
                algorithm="RS256",
            )
        except Exception:
            errors.append("fcm_private_key_invalid")

    return {
        "configured": configured,
        "valid": configured and not errors,
        "errors": errors,
        "transport": "fcm-http-v1",
    }
