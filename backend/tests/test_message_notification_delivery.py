import asyncio
import unittest
from uuid import UUID

from components.notification.message_delivery import (
    DEFAULT_MESSAGE_NOTIFICATION_PREFERENCES,
    SURFACE_MESSENGER,
    SURFACE_SPACE,
    message_delivery_policy,
)
from components.realtime import realtime_service
from components.realtime.active_context import active_context_service
from settings import config


class MessageDeliveryPolicyTests(unittest.TestCase):
    def test_online_messenger_alerts_when_context_is_not_active(self):
        policy = message_delivery_policy(
            SURFACE_MESSENGER,
            online=True,
            active_context=False,
        )
        self.assertTrue(policy["notify_in_app"])
        self.assertTrue(policy["play_sound"])
        self.assertFalse(policy["external_eligible"])

    def test_backgrounded_online_socket_remains_push_eligible(self):
        prefs = dict(DEFAULT_MESSAGE_NOTIFICATION_PREFERENCES)
        prefs["web_push_messenger"] = True
        prefs["native_push_messenger"] = True
        policy = message_delivery_policy(
            SURFACE_MESSENGER, online=True, active_context=False, preferences=prefs,
        )
        self.assertTrue(policy["web_push_eligible"])
        self.assertTrue(policy["native_push_eligible"])
        self.assertTrue(policy["external_eligible"])
        self.assertFalse(policy["email_nudge_eligible"])

    def test_active_messenger_context_suppresses_duplicate_alert(self):
        policy = message_delivery_policy(
            SURFACE_MESSENGER,
            online=True,
            active_context=True,
        )
        self.assertFalse(policy["notify_in_app"])
        self.assertFalse(policy["play_sound"])

    def test_sound_can_be_muted_without_disabling_in_app_alert(self):
        preferences = dict(DEFAULT_MESSAGE_NOTIFICATION_PREFERENCES)
        preferences["messenger_sound"] = False
        policy = message_delivery_policy(
            SURFACE_MESSENGER,
            online=True,
            active_context=False,
            preferences=preferences,
        )
        self.assertTrue(policy["notify_in_app"])
        self.assertFalse(policy["play_sound"])

    def test_offline_messenger_can_be_eligible_for_opt_in_external_nudge(self):
        preferences = dict(DEFAULT_MESSAGE_NOTIFICATION_PREFERENCES)
        preferences["email_unread_dm_nudge"] = True
        policy = message_delivery_policy(
            SURFACE_MESSENGER,
            online=False,
            active_context=False,
            preferences=preferences,
        )
        self.assertFalse(policy["notify_in_app"])
        self.assertFalse(policy["play_sound"])
        self.assertTrue(policy["email_nudge_eligible"])
        self.assertTrue(policy["external_eligible"])

    def test_offline_space_never_becomes_external_reengagement(self):
        preferences = dict(DEFAULT_MESSAGE_NOTIFICATION_PREFERENCES)
        preferences["web_push_space"] = True
        policy = message_delivery_policy(
            SURFACE_SPACE,
            online=False,
            active_context=False,
            preferences=preferences,
        )
        self.assertFalse(policy["notify_in_app"])
        self.assertFalse(policy["play_sound"])
        self.assertFalse(policy["web_push_eligible"])
        self.assertFalse(policy["external_eligible"])

    def test_in_app_preference_does_not_turn_into_transport_authorization(self):
        preferences = dict(DEFAULT_MESSAGE_NOTIFICATION_PREFERENCES)
        preferences["messenger_in_app"] = False
        policy = message_delivery_policy(
            SURFACE_MESSENGER,
            online=True,
            active_context=False,
            preferences=preferences,
        )
        self.assertFalse(policy["notify_in_app"])
        self.assertFalse(policy["play_sound"])
        # The policy intentionally has no allow_message/deny_message result.
        self.assertNotIn("allow_message", policy)


class ActiveContextFallbackTests(unittest.TestCase):
    def test_messenger_context_is_connection_scoped_and_clearable(self):
        async def run_case():
            original_debug = config.DEBUG
            account_uid = UUID("00000000-0000-0000-0000-000000000701")
            dialog_uid = UUID("00000000-0000-0000-0000-000000000702")
            active_context_service._fallback.clear()
            try:
                config.DEBUG = True
                await active_context_service.set_messenger(
                    "notification-test-connection",
                    account_uid,
                    dialog_uid,
                )
                self.assertTrue(
                    await active_context_service.is_active(
                        account_uid,
                        SURFACE_MESSENGER,
                        dialog_uid,
                    )
                )
                await active_context_service.clear_messenger(
                    "notification-test-connection",
                    account_uid,
                    dialog_uid,
                )
                self.assertFalse(
                    await active_context_service.is_active(
                        account_uid,
                        SURFACE_MESSENGER,
                        dialog_uid,
                    )
                )
            finally:
                active_context_service._fallback.clear()
                config.DEBUG = original_debug

        asyncio.run(run_case())

    def test_space_context_reuses_distributed_room_presence_contract(self):
        async def run_case():
            account_uid = UUID("00000000-0000-0000-0000-000000000703")
            room_uid = UUID("00000000-0000-0000-0000-000000000704")
            connection_id = "notification-space-context"
            await realtime_service.register_connection(
                connection_id=connection_id,
                user_uid=account_uid,
                target="room",
                room_uid=room_uid,
            )
            try:
                self.assertTrue(
                    await active_context_service.is_active(
                        account_uid,
                        SURFACE_SPACE,
                        room_uid,
                    )
                )
            finally:
                await realtime_service.unregister_connection(connection_id)

        asyncio.run(run_case())


if __name__ == "__main__":
    unittest.main()
