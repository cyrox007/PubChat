import os
import unittest
from pathlib import Path
from uuid import uuid4

os.environ.setdefault("JWT_ACCESS_SECRET_KEY", "test-access-secret-value-at-least-32-characters")
os.environ.setdefault("JWT_REFRESH_SECRET_KEY", "test-refresh-secret-value-at-least-32-characters")
os.environ.setdefault("CSRF_SECRET_KEY", "test-csrf-secret-value-at-least-32-characters")
os.environ.setdefault("DEBUG", "True")

from services.auth_service import generate_tokens
from utils.jwt import validate_access_token, validate_refresh_token


ROOT = Path(__file__).resolve().parents[1]


class MultiDeviceSessionContractTests(unittest.TestCase):
    def test_identity_tokens_preserve_session_and_device_binding(self):
        account_uid = str(uuid4())
        session_uid = str(uuid4())
        device_uid = str(uuid4())
        tokens = generate_tokens(
            account_uid,
            session_uid=session_uid,
            device_uid=device_uid,
        )

        access = validate_access_token(tokens["access"])
        refresh = validate_refresh_token(tokens["refresh"])
        for payload in (access, refresh):
            self.assertEqual(payload["user_uid"], account_uid)
            self.assertEqual(payload["session_uid"], session_uid)
            self.assertEqual(payload["device_uid"], device_uid)

    def test_legacy_tokens_without_session_binding_remain_valid(self):
        account_uid = str(uuid4())
        tokens = generate_tokens(account_uid)
        access = validate_access_token(tokens["access"])
        self.assertEqual(access, {"user_uid": account_uid})

    def test_session_routes_and_realtime_control_are_wired(self):
        identity_routes = (ROOT / "views/identity/routers.py").read_text(encoding="utf-8")
        realtime_routes = (ROOT / "views/realtime/routers.py").read_text(encoding="utf-8")
        websocket_auth = (ROOT / "views/realtime/ws_auth.py").read_text(encoding="utf-8")
        manager = (ROOT / "socket_manager/manager.py").read_text(encoding="utf-8")

        self.assertIn('@router.get("/sessions")', identity_routes)
        self.assertIn('@router.delete("/sessions/{session_uid}")', identity_routes)
        self.assertIn('@router.delete("/devices/{device_uid}")', identity_routes)
        self.assertIn('@router.post("/sessions/revoke-others")', identity_routes)
        self.assertIn('"kind": "session_control"', identity_routes)
        self.assertIn('session_uid=current_user.get("session_uid")', realtime_routes)
        self.assertIn('device_uid=current_user.get("device_uid")', realtime_routes)
        self.assertIn("active_identity_session", websocket_auth)
        self.assertIn('websocket.state.session_uid', websocket_auth)
        self.assertIn('kind == "session_control"', manager)
        self.assertIn("except_session_uid", manager)

    def test_device_id_is_persisted_without_token_authority(self):
        service = (ROOT / "components/identity/service.py").read_text(encoding="utf-8")
        migration = (ROOT / "alembic/versions/u9j5m3i88009_multi_device_sessions.py").read_text(encoding="utf-8")
        self.assertIn('DEVICE_ID_HEADER = "X-PubChat-Device-ID"', service)
        self.assertIn("return uuid4()", service)
        self.assertIn("device_uid = uid", migration)
        self.assertIn("ix_identity_sessions_account_device", migration)


if __name__ == "__main__":
    unittest.main()
