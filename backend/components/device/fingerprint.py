import base64
import hashlib


def _key_bytes(value: str) -> bytes:
    padding = "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode(value + padding)


def device_fingerprint(identity_signing_key: str, identity_dh_key: str) -> str:
    digest = hashlib.sha256(
        b"pubchat-device-identity-v1\x00"
        + _key_bytes(identity_signing_key)
        + _key_bytes(identity_dh_key)
    ).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
