# E2EE device verification and safety numbers

PubChat's text E2EE can encrypt to a device without the server learning the plaintext, but encryption alone does not prove that a newly presented device really belongs to the person the user intends to contact. This layer adds local device-change awareness and explicit human verification.

## Verification model

Verification is deliberately client-owned. The server publishes public device identity material, but it cannot set a device to `verified` and it does not receive the user's local verification decision.

For every active peer device the current device derives a **pairwise safety number** from both sides' Account IDs, device IDs, Ed25519 signing public keys and X25519 identity public keys. The two device descriptors are sorted canonically before hashing, so both participants derive the same code when comparing the same pair of devices.

The safety-number domain is:

`pubchat-safety-number-v1\0`

followed by the canonical JSON descriptors of both devices, separated by a zero byte, then SHA-256. The digest is rendered as eight five-digit groups for manual comparison.

A verification record is scoped to:

- the current local device UID;
- the peer device UID;
- the peer device fingerprint;
- the exact derived safety number.

Changing the current device therefore requires verification again. A changed peer fingerprint also invalidates the old verification automatically.

## Local-only state

Verification records and acknowledged peer-device directory snapshots live in the existing origin-scoped `pubchat-e2ee-sessions-v1` IndexedDB `pins` store under namespaced synthetic keys. No schema-version bump is required, so the verification layer remains compatible with the existing E2EE session database.

The local state is cleared together with the E2EE session database when the current cryptographic device is revoked.

## Device directory changes

On first observation PubChat records the peer's active cryptographic device directory as the initial acknowledged snapshot without claiming that any device is verified.

Later differences are shown as a security warning:

- newly added device;
- removed device;
- changed identity fingerprint for an existing device UID.

The user can inspect the current devices and acknowledge the directory change. Acknowledging a device-list change is **not** the same as verifying its safety number. The conversation remains `unverified` until every active peer device has been explicitly compared and marked verified from the current local device.

This distinction avoids turning a generic “OK” button into a cryptographic trust decision.

## Messenger UX states

The compact security panel above the Messenger composer has four meaningful states:

- **verified** — every current peer device has a matching local verification record;
- **unverified** — E2EE devices exist, but at least one has not been manually checked;
- **changed** — the current peer device directory differs from the locally acknowledged snapshot;
- **unavailable** — the peer has no registered E2EE devices.

For each device the UI shows a pairwise safety number, copy action, explicit `Код совпал` action and the ability to remove local verification.

The copy payload also contains a structured `pubchat-safety-number-v1` JSON representation so a later QR scanner can use exactly the same canonical verification material without introducing a second verification protocol.

## What this protects

Manual comparison over an independent channel can detect a server or network path presenting different device identity material to the two participants for the device pair they compare. It also makes subsequent device additions visible relative to the locally acknowledged directory.

## Remaining limitations

This phase does not create a server-side web-of-trust, does not synchronize `verified` state between the user's own devices, and does not yet include a camera QR scanner/rendered QR code. Copyable structured safety payloads intentionally prepare that next UI step.

Directory checks are performed when the security panel loads/refetches; they are not yet cryptographically serialized with every outgoing send. Consequently this improves TOFU/device-change awareness but should not yet be described as strict malicious-server-resistant key transparency.

The next hardening step can make a previously verified conversation fail closed on an unacknowledged device-directory change, then add QR comparison and an append-only/key-transparency mechanism if PubChat needs stronger server-equivocation resistance.
