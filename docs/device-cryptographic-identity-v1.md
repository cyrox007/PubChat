# Device cryptographic identity v1

This document defines PubChat's first device-level cryptographic identity contract. It is infrastructure for future end-to-end encrypted Messenger sessions and verified call identity. **It does not enable E2EE message transport by itself.** Existing Messenger message bodies continue to use the current server-readable contract until the later session/envelope phase is implemented.

## Security boundary

A PubChat Account may have multiple cryptographic devices. Each device owns its own long-term Ed25519 signing identity, long-term X25519 Diffie-Hellman identity, rotating X25519 signed prekey and a pool of one-time X25519 prekeys.

The backend stores only public material and lifecycle metadata. Private keys are not accepted by any API field and have no database columns. A browser client stores private `CryptoKey` objects in origin-scoped IndexedDB. Generated private key material is re-imported as `extractable=false` before durable storage; temporary PKCS#8 bytes used for that transition are overwritten immediately after import. This reduces accidental JavaScript export/exfiltration but is not a substitute for an OS hardware keystore or protection from a fully compromised browser origin.

The current browser implementation requires a secure context, IndexedDB and native Web Crypto support for Ed25519 and X25519. Unsupported clients fail explicitly with `crypto_unsupported`; they do not silently downgrade an encrypted protocol because encrypted message transport is not enabled yet.

## Device identity

A client creates a random `device_uid` and keeps it stable across ordinary login and refresh-token rotation. The device UID is not derived from a refresh token, IP address, User-Agent or Persona.

For one `device_uid`, these values are immutable:

- `key_version`
- Ed25519 `identity_signing_key`
- X25519 `identity_dh_key`

Trying to register the same device UID with different identity material is rejected. Intentional long-term identity rotation is represented as a new cryptographic device, followed by revocation of the old device. This makes identity changes observable rather than silently replacing trust material.

The human-readable `device_label` is metadata only and has no cryptographic authority.

## Signed prekey

Each device publishes one rotating X25519 signed prekey. The browser signs the domain-separated structure:

`pubchat-signed-prekey-v1\0 || uint32(prekey_id) || raw_x25519_public_key`

with the device Ed25519 identity key.

The server validates encoding, lengths and IDs but does **not** treat the signature as trusted merely because it was uploaded. A peer can verify the signature with `verifySignedPrekey()` before using the bundle during future session establishment. The server therefore cannot turn an invalid signed-prekey signature into a valid one by changing a boolean field.

Reusing the current signed-prekey ID with different public key material is rejected.

## One-time prekeys

A device may upload up to 100 one-time prekeys per request and keep at most 200 unclaimed one-time prekeys on the server. Key IDs are unique within the device.

When a peer requests a prekey bundle, the backend selects at most one unused one-time prekey per active target device using `FOR UPDATE SKIP LOCKED`, marks it claimed and commits the claim. Concurrent session starters therefore cannot intentionally receive the same available row from the same transaction window.

A bundle still works when a device temporarily has no one-time prekey: its long-term identity and signed prekey remain present and `one_time_prekey` is `null`. The later E2EE session protocol must decide whether that state is acceptable or whether it should wait for replenishment.

## Multi-device bundle

`GET /crypto/v1/accounts/{account_uid}/prekey-bundle` returns the public bundle for every non-revoked cryptographic device of the target Account. The request is available only when the existing direct-message privacy/block policy allows the requester to contact the target. A denied lookup returns a generic not-available response rather than revealing whether the target has registered cryptographic devices.

A future encrypted sender must establish/encrypt separately for every eligible target device. Persona changes never create a separate security identity and therefore cannot bypass Account-level device trust.

## Device revocation

`DELETE /crypto/v1/devices/{device_uid}` marks the device revoked and deletes its unused one-time prekeys. Revoked devices are omitted from future bundles. Revocation is Account-owned and cannot be undone by re-registering the same device UID.

The current browser helper `revokeCurrentCryptoDevice()` revokes the server record first and only then clears the local IndexedDB identity. This ordering prevents an offline local deletion from pretending that the server-side device has been revoked.

Device cryptographic revocation does not yet revoke an HTTP login session automatically. Authentication sessions and E2EE device identities are deliberately separate lifecycles; a later device-management UI may offer combined actions such as “sign out and revoke encryption device”.

## Fingerprints and verification

The server and client-facing projection uses a deterministic device fingerprint based on:

`SHA-256("pubchat-device-identity-v1\\0" || raw_ed25519_public || raw_x25519_public)`

The fingerprint is a stable identifier for comparison, not proof by itself. A later verification UX can render it as safety numbers/QR data and bind it to a verified Account/device relationship. Verified WebRTC calls can then bind their handshake to the same device signing identity rather than trusting signaling-provided fingerprints alone.

## API

Authenticated device-owner operations:

- `POST /crypto/v1/devices` — register/idempotently refresh the same immutable device identity and upload prekeys.
- `GET /crypto/v1/devices` — list own active and revoked cryptographic devices plus available prekey counts.
- `PUT /crypto/v1/devices/{device_uid}/signed-prekey` — rotate the device signed prekey.
- `POST /crypto/v1/devices/{device_uid}/one-time-prekeys` — replenish one-time prekeys.
- `DELETE /crypto/v1/devices/{device_uid}` — revoke the device.

Peer operation:

- `GET /crypto/v1/accounts/{account_uid}/prekey-bundle` — atomically claim one prekey per active target device, subject to the existing DM privacy/block policy.

## Browser workflow

`frontend/src/crypto/deviceIdentity.js` provides local key generation/storage and signed-prekey verification. `frontend/src/crypto/deviceIdentitySync.js` provides explicit server synchronization helpers.

The foundation is intentionally **not auto-bootstrapped on login**. Creating cryptographic identity remains an explicit preparatory operation until encrypted Messenger envelopes are implemented, so older browsers and existing sessions are not accidentally forced into a half-encrypted state.

## Next phase

The next E2EE phase must add a peer session/envelope protocol rather than merely setting an `encrypted=true` flag. At minimum it needs authenticated session establishment using these device bundles, per-device message encryption, replay/order handling, ratcheting/key rotation, device-list change handling, verification state and migration behavior for existing plaintext conversations.
