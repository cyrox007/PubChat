from datetime import datetime
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import FastAPI, HTTPException

from components.message.model import PrivateMessage
from views.messages import routers as message_routes


class MessengerMutationEncryptionGateTests(IsolatedAsyncioTestCase):
    def setUp(self):
        self.app = FastAPI()
        message_routes.install(self.app)
        self.routes = {(route.path, method): route.endpoint for route in self.app.routes for method in (getattr(route, 'methods', None) or ())}
        self.sender = uuid4()
        self.receiver = uuid4()
        self.message_uid = uuid4()
        self.source = SimpleNamespace(
            uid=self.message_uid,
            sender_uid=self.sender,
            receiver_uid=self.receiver,
            text="existing plaintext",
            content_type="text",
            media_metadata={},
            created_at=datetime.utcnow(),
        )
        self.db = object()
        self.session = {"user_uid": str(self.sender)}

    def denial(self):
        return HTTPException(
            status_code=409,
            detail={"error_type": "conversation_requires_e2ee"},
        )

    async def test_reply_cannot_write_plaintext_to_e2ee_dialog(self):
        endpoint = self.routes[("/messages/v2/{surface}/{message_uid}/reply", "POST")]
        with (
            patch.object(message_routes, "load_message", new_callable=AsyncMock, return_value=self.source),
            patch.object(message_routes, "ensure_message_access", new_callable=AsyncMock),
            patch.object(message_routes, "assert_allowed", new_callable=AsyncMock),
            patch.object(message_routes, "_dm_allowed", new_callable=AsyncMock, return_value=True),
            patch.object(message_routes, "assert_plaintext_allowed", new_callable=AsyncMock) as policy,
            patch.object(PrivateMessage, "create_private_message", new_callable=AsyncMock) as persist,
        ):
            policy.side_effect = self.denial()
            with self.assertRaises(HTTPException) as caught:
                await endpoint(
                    surface="messenger", message_uid=self.message_uid,
                    payload=message_routes.ReplyMessageRequest(content="secret"),
                    current_user=self.session, db=self.db,
                )
            self.assertEqual(caught.exception.status_code, 409)
            policy.assert_awaited_once_with(self.db, self.sender, self.receiver)
            persist.assert_not_awaited()

    async def test_edit_cannot_publish_plaintext_after_mode_switch(self):
        endpoint = self.routes[("/messages/v2/{surface}/{message_uid}", "PATCH")]
        with (
            patch.object(message_routes, "load_message", new_callable=AsyncMock, return_value=self.source),
            patch.object(message_routes, "ensure_message_access", new_callable=AsyncMock) as access,
            patch.object(message_routes, "assert_allowed", new_callable=AsyncMock),
            patch.object(message_routes, "assert_plaintext_allowed", new_callable=AsyncMock) as policy,
            patch.object(message_routes, "edit_message", new_callable=AsyncMock) as edit,
        ):
            policy.side_effect = self.denial()
            with self.assertRaises(HTTPException) as caught:
                await endpoint(
                    surface="messenger", message_uid=self.message_uid,
                    payload=message_routes.EditMessageRequest(content="secret"),
                    current_user=self.session, db=self.db,
                )
            self.assertEqual(caught.exception.status_code, 409)
            access.assert_awaited_once_with(self.db, "messenger", self.source, self.sender, write=True)
            policy.assert_awaited_once_with(self.db, self.sender, self.receiver)
            edit.assert_not_awaited()

    async def test_forward_cannot_create_plaintext_in_e2ee_target(self):
        endpoint = self.routes[("/messages/v2/{surface}/{message_uid}/forward", "POST")]
        with (
            patch.object(message_routes, "load_message", new_callable=AsyncMock, return_value=self.source),
            patch.object(message_routes, "ensure_message_access", new_callable=AsyncMock),
            patch.object(message_routes, "assert_allowed", new_callable=AsyncMock),
            patch.object(message_routes, "_dm_allowed", new_callable=AsyncMock, return_value=True),
            patch.object(message_routes, "assert_plaintext_allowed", new_callable=AsyncMock) as policy,
            patch.object(PrivateMessage, "create_private_message", new_callable=AsyncMock) as persist,
        ):
            policy.side_effect = self.denial()
            with self.assertRaises(HTTPException) as caught:
                await endpoint(
                    surface="messenger", message_uid=self.message_uid,
                    payload=message_routes.ForwardMessageRequest(target_surface="messenger", target_uid=self.receiver),
                    current_user=self.session, db=self.db,
                )
            self.assertEqual(caught.exception.status_code, 409)
            policy.assert_awaited_once_with(self.db, self.sender, self.receiver)
            persist.assert_not_awaited()

    async def test_plaintext_reply_still_works_when_server_allows_it(self):
        endpoint = self.routes[("/messages/v2/{surface}/{message_uid}/reply", "POST")]
        created = {"uid": str(uuid4()), "content": "hello", "content_type": "text"}
        with (
            patch.object(message_routes, "load_message", new_callable=AsyncMock, return_value=self.source),
            patch.object(message_routes, "ensure_message_access", new_callable=AsyncMock),
            patch.object(message_routes, "assert_allowed", new_callable=AsyncMock),
            patch.object(message_routes, "_dm_allowed", new_callable=AsyncMock, return_value=True),
            patch.object(message_routes, "assert_plaintext_allowed", new_callable=AsyncMock) as policy,
            patch.object(PrivateMessage, "create_private_message", new_callable=AsyncMock, return_value=created) as persist,
            patch.object(message_routes.private_manager, "send_to_user", new_callable=AsyncMock) as delivery,
            patch.object(message_routes, "inspect_plaintext_write", new_callable=AsyncMock) as preflight,
        ):
            result = await endpoint(
                surface="messenger", message_uid=self.message_uid,
                payload=message_routes.ReplyMessageRequest(content="hello"),
                current_user=self.session, db=self.db,
            )
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["message"], created)
            policy.assert_awaited_once_with(self.db, self.sender, self.receiver)
            persist.assert_awaited_once()
            preflight.assert_awaited_once_with(self.db, "hello", surface="messenger_plaintext", operation="reply")
            self.assertEqual(delivery.await_count, 2)

    async def test_existing_ciphertext_cannot_be_edited_or_replied_as_text(self):
        self.source.content_type = "e2ee"
        with (
            patch.object(message_routes, "load_message", new_callable=AsyncMock, return_value=self.source),
            patch.object(message_routes, "ensure_message_access", new_callable=AsyncMock),
            patch.object(message_routes, "assert_allowed", new_callable=AsyncMock),
            patch.object(message_routes, "edit_message", new_callable=AsyncMock) as edit,
            patch.object(PrivateMessage, "create_private_message", new_callable=AsyncMock) as persist,
        ):
            for path, payload in (
                ("/messages/v2/{surface}/{message_uid}", message_routes.EditMessageRequest(content="text")),
                ("/messages/v2/{surface}/{message_uid}/reply", message_routes.ReplyMessageRequest(content="text")),
            ):
                method = "PATCH" if path == "/messages/v2/{surface}/{message_uid}" else "POST"
                with self.assertRaises(HTTPException) as caught:
                    await self.routes[(path, method)](
                        surface="messenger", message_uid=self.message_uid,
                        payload=payload, current_user=self.session, db=self.db,
                    )
                self.assertEqual(caught.exception.status_code, 409)
            edit.assert_not_awaited()
            persist.assert_not_awaited()

    async def test_existing_envelope_cannot_be_forwarded_without_device_envelopes(self):
        self.source.content_type = "e2ee"
        endpoint = self.routes[("/messages/v2/{surface}/{message_uid}/forward", "POST")]
        with (
            patch.object(message_routes, "load_message", new_callable=AsyncMock, return_value=self.source),
            patch.object(message_routes, "ensure_message_access", new_callable=AsyncMock),
            patch.object(PrivateMessage, "create_private_message", new_callable=AsyncMock) as persist,
        ):
            with self.assertRaises(HTTPException) as caught:
                await endpoint(
                    surface="messenger", message_uid=self.message_uid,
                    payload=message_routes.ForwardMessageRequest(target_surface="messenger", target_uid=self.receiver),
                    current_user=self.session, db=self.db,
                )
            self.assertEqual(caught.exception.status_code, 409)
            persist.assert_not_awaited()
