import unittest

from app import create_app
from components.device.directory_transparency import (
    GENESIS_HASH,
    TRANSPARENCY_VERSION,
    canonical_directory_hash,
)
from components.device.directory_transparency_model import DeviceDirectoryEvent


class DeviceDirectoryTransparencyContractTests(unittest.TestCase):
    def test_event_schema_is_account_scoped_append_only_shape(self):
        columns = set(DeviceDirectoryEvent.__table__.c.keys())
        for name in {
            "account_uid",
            "sequence",
            "event_type",
            "device_uid",
            "fingerprint",
            "previous_hash",
            "directory_hash",
            "event_hash",
            "created_at",
        }:
            self.assertIn(name, columns)
        constraints = {
            constraint.name
            for constraint in DeviceDirectoryEvent.__table__.constraints
            if constraint.name
        }
        self.assertIn("uq_device_directory_event_sequence", constraints)
        self.assertIn("uq_device_directory_event_hash", constraints)

    def test_directory_hash_is_order_independent_and_identity_bound(self):
        first = {
            "device_uid": "00000000-0000-0000-0000-000000000001",
            "key_version": 1,
            "fingerprint": "fingerprint-a",
            "identity_signing_key": "signing-a",
            "identity_dh_key": "dh-a",
        }
        second = {
            "device_uid": "00000000-0000-0000-0000-000000000002",
            "key_version": 1,
            "fingerprint": "fingerprint-b",
            "identity_signing_key": "signing-b",
            "identity_dh_key": "dh-b",
        }
        self.assertEqual(
            canonical_directory_hash([first, second]),
            canonical_directory_hash([second, first]),
        )
        modified = dict(second)
        modified["identity_dh_key"] = "dh-changed"
        self.assertNotEqual(
            canonical_directory_hash([first, second]),
            canonical_directory_hash([first, modified]),
        )

    def test_protocol_constants_are_versioned(self):
        self.assertEqual(TRANSPARENCY_VERSION, "pubchat-device-directory-v1")
        self.assertEqual(GENESIS_HASH, "0" * 64)

    def test_checkpoint_and_history_routes_are_installed(self):
        paths = {route.path for route in create_app().routes}
        self.assertIn("/crypto/v1/accounts/{target_account_uid}/devices", paths)
        self.assertIn("/crypto/v1/accounts/{target_account_uid}/directory-history", paths)


if __name__ == "__main__":
    unittest.main()
