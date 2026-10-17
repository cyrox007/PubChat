# Messenger E2EE v1

PubChat Messenger E2EE v1 encrypts **text direct messages** end-to-end between registered cryptographic devices. The server routes ciphertext and retains delivery metadata, but it does not receive the text plaintext for v1-encrypted messages.

This phase builds on `device-cryptographic-identity-v1.md`. Existing historical plaintext messages remain plaintext. Media/file/voice messages are not migrated to this protocol in v1 and continue to use the existing transport until encrypted attachment envelopes are implemented.

## Threat boundary

The v1 protocol protects message text against disclosure from the application database, backups, logs and ordinary server-side message handling. The server can see sender/receiver Account IDs, device routing IDs, timestamps, message existence/size, session IDs and counters.

Each device keeps X25519/Ed25519 private key material in its browser origin. E2EE session chain keys and cached per-message history keys are stored as non-extractable Web Crypto `CryptoKey` objects in IndexedDB.

A fully compromised client origin can still read plaintext while the user is using that origin. Likewise, v1 does not yet claim protection against a malicious server that introduces an entirely new unverified device identity for an Account. Device keys are TOFU-pinned locally, and a changed identity for the same device UID is rejected, but cross-device safety-number/QR verification is a later phase.

## Session bootstrap

For each sender-device → recipient-device direction PubChat establishes an independent outbound session. The sender verifies the recipient's Ed25519 signature over its signed X25519 prekey before using it.

The initial shared root is derived from three X25519 DH values, plus a fourth when a one-time prekey is available:

1. sender identity DH × recipient signed prekey;
2. sender ephemeral DH × recipient identity DH;
3. sender ephemeral DH × recipient signed prekey;
4. optional sender ephemeral DH × recipient one-time prekey.

The concatenated DH output is fed through HKDF-SHA-256 with the `pubchat-e2ee-root-v1` domain. The resulting 32-byte value becomes the first HMAC-SHA-256 chain key.

The initial envelope header contains only public/session bootstrap material: sender public identities, sender ephemeral X25519 public key, recipient signed-prekey ID and optional one-time-prekey ID. The backend verifies that the sender identity in the header matches the authenticated sender device and that the referenced signed-prekey ID is still current for the target device.

## Symmetric ratchet

Every outbound device session has its own monotonically increasing `counter`.

For counter `n`:

- message key = HMAC(chain_key, `pubchat-message-key-v1:n`);
- next chain key = HMAC(chain_key, `pubchat-chain-key-v1:n`).

The message key is imported as AES-256-GCM. The next chain key replaces the previous chain key. The old chain key is not persisted after the ratchet advances.

AES-GCM associated data binds:

- protocol version;
- sender device UID;
- recipient device UID;
- session UUID;
- counter.

This prevents ciphertext from being moved to another device/session/counter without authentication failure.

The receiver accepts a forward gap of at most 64 counters and derives intermediate message keys so out-of-order delivery can still be decrypted. Per-message keys are retained locally for conversation history; this is intentionally separate from the forward-only session chain. A compromise of local unlocked history storage can therefore expose locally retained history even though the server never receives those keys.

This is a **symmetric chain ratchet**, not yet a full bidirectional DH Double Ratchet. A reply uses a separately bootstrapped sender-device → recipient-device outbound session. A later phase may add periodic DH ratchet steps without changing the server envelope model.

## Multi-device fan-out

Before an encrypted send, the client obtains the active cryptographic device directory for both Accounts. The sender creates one ciphertext envelope for **every active device of the recipient and every active device of itself**.

The backend independently loads the current device list and rejects the send with `e2ee_device_list_changed` if any active device is missing. This prevents a stale client from silently encrypting only to a subset of devices after a new device was added.

A new recipient session claims an optional one-time prekey from the existing prekey-bundle API. Existing sessions use the public device directory and do not consume additional one-time prekeys.

Revoked devices are excluded from new sends. Revoking the current local cryptographic device also clears its local E2EE session database so a newly generated device identity cannot accidentally reuse chains created by the old identity.

## Server persistence

An encrypted DM is represented by:

- one ordinary `private_messages` row with `content_type = "e2ee"`, `text = NULL` and only protocol metadata;
- one `private_message_envelopes` row per target device.

Envelope rows contain ciphertext, nonce, target device/account, sender device, session ID, counter and optional initial public header. There is no plaintext/content column in the envelope table.

Database uniqueness enforces:

- one envelope per `(message, recipient_device)`;
- one persisted message per `(recipient_device, session_id, counter)`.

The second constraint prevents a client from persisting the same ratchet counter as two distinct messages even if it changes its request id.

## Transport and fallback

Encrypted text is sent through authenticated `POST /crypto/v1/messages`. Realtime delivery still uses the existing Messenger user channel, but only the ciphertext envelopes for the receiving Account are included.

Conversation history is loaded through the existing Messenger conversation contract. For rows with `content_type = "e2ee"`, the client then requests only the envelope rows that belong to its authenticated Account and decrypts the envelope addressed to the current device.

A text message falls back to the legacy plaintext transport **only when the peer has no registered cryptographic devices**. If encryption is expected and cryptographic setup/encryption fails, the client blocks the send rather than silently downgrading it.

Media/file/voice messages are outside v1 and continue through the legacy path; the UI must not label those messages as E2EE.

## Notifications

The backend's notification pipeline receives no encrypted text body. Push/in-app delivery continues to use generic Messenger notification metadata. The decrypted message text exists only in the receiving client after envelope decryption.

## Moderation caveat

Server-side moderation cannot inspect v1 E2EE text because the server does not possess plaintext or message keys. The existing report action can still identify the encrypted message row, but a complete E2EE-aware abuse report flow must explicitly allow the reporting client to attach the selected decrypted message/evidence with user consent. That evidence flow is a separate Trust & Safety task and must not become a hidden backdoor for routine server-side decryption.

## Next cryptographic work

After this phase, the next security increments are:

- encrypted attachment/media keys and ciphertext upload;
- safety-number / QR verification UX and verified-device state;
- explicit device-change warnings;
- optional DH Double Ratchet re-keying for long-lived sessions;
- consent-driven encrypted-message evidence for Trust & Safety;
- binding WebRTC call identity to verified device signing identities.
