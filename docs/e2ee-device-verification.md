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

### QR comparison

The security panel can render the current pairwise safety number as a local QR code. The QR payload is intentionally small and versioned:

`pubchat-e2ee-v1:<40 decimal safety-number digits>`

The QR image is generated entirely in the browser. No safety number, Account/device identifier, public key or verification payload is sent to a third-party QR service.

On browsers with `BarcodeDetector` QR support, PubChat can use the device camera to scan the peer's QR locally. A scan marks a device verified only if the decoded versioned payload exactly equals the safety number PubChat has just derived for the selected current device pair. A mismatched, malformed or unversioned QR never sets local verification state. Browsers without local QR detection expose a manual paste fallback for a QR value read by the system camera or another trusted device.

QR comparison changes only the ergonomics of independent verification; it does not make the PubChat server a trusted attester.

## Device changes

The browser stores the last acknowledged public device directory for the peer. A newly added device, a removed device, or a different identity key under an existing device ID changes the directory state and produces **Требуется повторная проверка**. Existing verification records only remain valid while their exact safety number and peer-device fingerprint still match.

Acknowledging that the directory changed is not the same as verifying the new key. New or changed devices still require an explicit safety-number comparison.

### Fail-closed send boundary

An E2EE send re-reads the current peer-device directory immediately before building encrypted envelopes and compares it with the locally acknowledged snapshot. If the directory differs, PubChat refuses to create or submit the encrypted message with `e2ee_peer_directory_unacknowledged` and refreshes the Messenger security panel.

The first observed directory is a trust-on-first-use baseline. After that baseline exists, additions, removals, or identity-key changes block new E2EE sends until the user explicitly acknowledges the changed directory. This acknowledgment only records that the user saw the new directory; it does not mark any new device as cryptographically verified.

When a fresh prekey bundle is claimed for a device, its Ed25519/X25519 identity keys must still match the directory entry used by the send check. A mismatch aborts the send instead of silently encrypting to a different identity.

## Device-directory transparency groundwork

Every Account with cryptographic devices now has a versioned append-only device-directory journal. Registration and revocation append an Account-scoped event with a monotonically increasing sequence, the previous event hash and a canonical hash of the current active device directory. Existing installations receive a migration-time bootstrap checkpoint representing the active directory at upgrade time.

`GET /crypto/v1/accounts/{account_uid}/devices` includes the latest `directory_checkpoint`. Authorized DM peers can retrieve subsequent journal events through `/directory-history`.

The browser stores the strongest checkpoint it has already observed for a peer in local E2EE IndexedDB state. Before `CryptoService.accountDevices()` returns a peer directory to any caller, PubChat validates that checkpoint:

- a lower sequence than the locally remembered value is rejected as rollback;
- a different hash at the same sequence is rejected as a fork;
- a higher sequence requires a contiguous `previous_hash -> event_hash` history from the locally stored checkpoint to the new checkpoint;
- history verification is bounded; excessively large gaps fail closed instead of doing unbounded work.

Because all Messenger E2EE peer-directory reads go through this common API client path, a consistency conflict blocks safety-number verification and encrypted-send preparation rather than becoming a cosmetic warning.

This is deliberately described as **transparency groundwork**, not as a complete public key-transparency system. The PubChat server still serves both the directory and its journal and can theoretically equivocate consistently to isolated clients. Full malicious-server resistance requires an independent witness/gossip mechanism, externally comparable signed checkpoints, or another anti-equivocation design. Local rollback/fork detection materially strengthens TOFU continuity but does not remove the server from the trust model.

## Storage and trust boundary

Manual verification state and remembered transparency checkpoints are stored locally in the same origin-scoped IndexedDB used by the browser E2EE session layer. They are not synchronized as server trust assertions and must be established independently on another device.

Safety-number or QR comparison remains the mechanism for users to independently detect substituted device identity keys. Directory checkpoints add continuity and auditability around subsequent server directory responses; they do not replace independent comparison.

## Relationship to conversation policy

`MESSENGER_E2EE_POLICY` and the per-conversation `plaintext|e2ee` setting determine which transport may be used. The earned E2EE privilege determines whether a user may switch an optional conversation into E2EE. Device verification does not change those policies and never turns a plaintext message into an encrypted one retroactively.
