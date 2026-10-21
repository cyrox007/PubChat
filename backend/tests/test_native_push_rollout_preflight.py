import unittest
from unittest.mock import patch

from workers import native_push_delivery as worker


class NativePushPreflightTests(unittest.TestCase):
    def test_refuses_missing_providers(self):
        with (
            patch("components.notification.native_push.fcm_configured", return_value=False),
            patch("components.notification.apns_push.apns_configured", return_value=False),
        ):
            self.assertEqual(worker.check_configuration(), 2)

    def test_accepts_apns_only_with_valid_signing(self):
        with (
            patch("components.notification.native_push.fcm_configured", return_value=False),
            patch("components.notification.apns_push.apns_configured", return_value=True),
            patch("components.notification.apns_push._apns_token", return_value="signed-jwt") as apns,
        ):
            self.assertEqual(worker.check_configuration(), 0)
            apns.assert_called_once()

    def test_accepts_fcm_only_with_valid_signing(self):
        with (
            patch("components.notification.native_push.fcm_configured", return_value=True),
            patch("components.notification.apns_push.apns_configured", return_value=False),
            patch("components.notification.native_push._fcm_service_account_email", return_value="service@example.test"),
            patch("components.notification.native_push._fcm_private_key", return_value="pem-private-key"),
            patch.object(worker.jwt, "encode", return_value="signed-jwt") as sign,
        ):
            self.assertEqual(worker.check_configuration(), 0)
            sign.assert_called_once()

    def test_invalid_fcm_key_fails_even_if_apns_is_configured(self):
        with (
            patch("components.notification.native_push.fcm_configured", return_value=True),
            patch("components.notification.apns_push.apns_configured", return_value=True),
            patch("components.notification.native_push._fcm_service_account_email", return_value="service@example.test"),
            patch("components.notification.native_push._fcm_private_key", return_value="bad-key"),
            patch.object(worker.jwt, "encode", side_effect=ValueError("secret should not enter logs")),
            patch("components.notification.apns_push._apns_token", return_value="signed-jwt"),
        ):
            self.assertEqual(worker.check_configuration(), 2)

    def test_does_not_send_or_connect_to_db(self):
        with (
            patch("components.notification.native_push.fcm_configured", return_value=False),
            patch("components.notification.apns_push.apns_configured", return_value=True),
            patch("components.notification.apns_push._apns_token", return_value="signed-jwt"),
            patch.object(worker, "run") as deliver,
            patch.object(worker.Database, "sessionmaker") as database,
        ):
            self.assertEqual(worker.check_configuration(), 0)
            deliver.assert_not_called()
            database.assert_not_called()


if __name__ == "__main__":
    unittest.main()
