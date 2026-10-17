import base64
import unittest
from uuid import uuid4

from pydantic import ValidationError

from app import create_app
from components.device.crypto_model import DeviceCryptographicIdentity, DeviceOneTimePreKey
from components.device.crypto_schemas import DeviceRegistrationRequest, OneTimePreKeyBatchRequest
from components.device.crypto_service import device_fingerprint


def _b64url(byte_value: int, length: int) -> str:
    return base64.urlsafe_b64encode(bytes([byte_value]) * length).decode("ascii").rstrip("=")


class DeviceCryptographicIdentityContractTests(unittest.TestCase):
    def _registration(self) -> dict:
        return {
            "device_uid": str(uuid4()),
            "device_label": "Android",
            "key_version": 1,
            "identity_signing_key": _b64url(1, 32),
            "identity_dh_key": _b64url(2, 32),
            "signed_prekey": {
                "id": 7,
                "public_key": _b64url(3, 32),
                "signature": _b64url(4, 64),
            },
            "one_time_prekeys": [
                {"id": 100, "public_key": _b64url(5, 32)},
                {"id": 101, "public_key": _b64url(6, 32)},
            ],
        }

    def test_registration_accepts_exact_public_key_and_signature_sizes(self):
        payload = DeviceRegistrationRequest.model_validate(self._registration())
        self.assertEqual(len(base64.urlsafe_b64decode(payload.identity_signing_key + "=")), 32)
        self.assertEqual(len(payload.one_time_prekeys), 2)

    def test_registration_rejects_invalid_key_material(self):
        data = self._registration()
        data["identity_signing_key"] = _b64url(1, 31)
        with self.assertRaises(ValidationError):
            DeviceRegistrationRequest.model_validate(data)

        data = self._registration()
        data["signed_prekey"]["signature"] = _b64url(4, 63)
        with self.assertRaises(ValidationError):
            DeviceRegistrationRequest.model_validate(data)

    def test_one_time_prekey_ids_must_be_unique(self):
        with self.assertRaises(ValidationError):
            OneTimePreKeyBatchRequest.model_validate(
                {
                    "one_time_prekeys": [
                        {"id": 9, "public_key": _b64url(1, 32)},
                        {"id": 9, "public_key": _b64url(2, 32)},
                    ]
                }
            )

    def test_fingerprint_is_deterministic_and_domain_separated(self):
        signing = _b64url(11, 32)
        dh = _b64url(12, 32)
        first = device_fingerprint(signing, dh)
        second = device_fingerprint(signing, dh)
        changed = device_fingerprint(signing, _b64url(13, 32))
        self.assertEqual(first, second)
        self.assertNotEqual(first, changed)
        self.assertEqual(len(base64.urlsafe_b64decode(first + "=")), 32)

    def test_server_schema_contains_public_material_only(self):
        device_columns = set(DeviceCryptographicIdentity.__table__.c.keys())
        prekey_columns = set(DeviceOneTimePreKey.__table__.c.keys())
        self.assertIn("identity_signing_key", device_columns)
        self.assertIn("identity_dh_key", device_columns)
        self.assertIn("signed_prekey_key", device_columns)
        self.assertIn("public_key", prekey_columns)
        forbidden = {"private_key", "identity_private_key", "secret_key", "private_key_material"}
        self.assertTrue(forbidden.isdisjoint(device_columns | prekey_columns))

    def test_crypto_routes_are_installed(self):
        paths = {route.path for route in create_app().routes}
        self.assertIn("/crypto/v1/devices", paths)
        self.assertIn("/crypto/v1/devices/{device_uid}/signed-prekey", paths)
        self.assertIn("/crypto/v1/devices/{device_uid}/one-time-prekeys", paths)
        self.assertIn("/crypto/v1/accounts/{target_account_uid}/prekey-bundle", paths)


if __name__ == "__main__":
    unittest.main()
