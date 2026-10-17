# E2EE device verification

PubChat direct-message E2EE uses Account-scoped cryptographic devices. The encryption privilege and device identity are separate concepts: reputation or an elevated platform role can allow an Account to enable optional E2EE, but neither reputation nor role proves that a particular cryptographic device belongs to the expected person.

## When verification is shown

The Messenger verification panel is available only when the current conversation actually has `effective_mode=e2ee` and both participants have active crypto devices (`crypto_ready=true`). Plaintext conversations do not expose safety numbers. If E2EE is selected but devices are not ready, the existing encryption control explains that readiness problem instead.

## Safety number

For every active peer device the browser derives a safety number from:

- both Account identifiers;
- the local device identifier;
- the peer device identifier;
- both devices' Ed25519 identity signing public keys;
- both devices' X25519 identity public keys.

The inputs are canonicalized and hashed with SHA-256 using a versioned PubChat domain separator. The displayed decimal groups are a human-comparable representation of that digest.

Users must compare the number through an independent trusted channel, for example in person or during a trusted voice/video conversation. Pressing **Код совпал** stores that manual decision locally for the current browser device.

## Device changes

The browser stores the last acknowledged public device directory for the peer. A newly added device, a removed device, or a different identity key under an existing device ID changes the directory state and produces **Требуется повторная проверка**. Existing verification records only remain valid while their exact safety number and peer-device fingerprint still match.

Acknowledging that the directory changed is not the same as verifying the new key. New or changed devices still require an explicit safety-number comparison.

### Fail-closed send boundary

An E2EE send re-reads the current peer-device directory immediately before building encrypted envelopes and compares it with the locally acknowledged snapshot. If the directory differs, PubChat refuses to create or submit the encrypted message with `e2ee_peer_directory_unacknowledged` and refreshes the Messenger security panel.

The first observed directory is a trust-on-first-use baseline. After that baseline exists, additions, removals, or identity-key changes block new E2EE sends until the user explicitly acknowledges the changed directory. This acknowledgment only records that the user saw the new directory; it does not mark any new device as cryptographically verified.

When a fresh prekey bundle is claimed for a device, its Ed25519/X25519 identity keys must still match the directory entry used by the send check. A mismatch aborts the send instead of silently encrypting to a different identity.

## Storage and trust boundary

Manual verification state is stored locally in the same origin-scoped IndexedDB used by the browser E2EE session layer. It is not synchronized as a server trust assertion and must be repeated independently on another device.

The current server remains the device-key directory. Safety-number comparison detects substitution when the two users compare independently, but PubChat does **not** yet provide a public key-transparency log or automatic malicious-directory-server resistance. QR comparison and key transparency are follow-up hardening items.

## Relationship to conversation policy

`MESSENGER_E2EE_POLICY` and the per-conversation `plaintext|e2ee` setting determine which transport may be used. The earned E2EE privilege determines whether a user may switch an optional conversation into E2EE. Device verification does not change those policies and never turns a plaintext message into an encrypted one retroactively.
