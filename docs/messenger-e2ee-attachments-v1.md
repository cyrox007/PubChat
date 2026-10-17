# Messenger E2EE attachments v1

PubChat E2EE attachments v1 extends the existing per-device Messenger E2EE protocol to images, video, audio, voice messages and ordinary files.

## Security boundary

Attachment bytes are encrypted in the browser before upload. The backend receives and stores only opaque AES-GCM ciphertext. It does not receive the attachment content key, AES-GCM nonce, original filename, original MIME type or original media kind.

The encrypted attachment's private descriptor is embedded inside the ordinary per-device E2EE message payload. Therefore every active device of both Accounts receives the attachment content key only after decrypting its own Messenger envelope.

The server can still observe unavoidable transport metadata: uploader Account, attachment UUID, ciphertext size/hash, upload/download timing and which private message references the blob. E2EE does not hide that metadata.

## Client encryption

For each attachment the sender creates:

- a random 256-bit AES content key;
- a random 96-bit AES-GCM nonce;
- a random attachment UUID.

AES-GCM associated data is the canonical JSON representation of:

`{ "v": "pubchat-e2ee-attachment-v1", "uid": "<attachment UUID>" }`

The ciphertext SHA-256 is calculated client-side. The browser uploads only ciphertext to `/crypto/v1/attachments/{attachment_uid}` and verifies that the server-reported size/hash match the bytes it sent.

The content key, nonce, original filename, MIME type, media kind, plaintext size, optional duration/waveform metadata and ciphertext hash are placed into a Messenger payload of type `attachment`. That payload is then protected by the existing device E2EE session and fan-out protocol.

If protected attachment delivery fails after upload, the client makes a best-effort request to delete the still-pending ciphertext blob. A blob that has already been atomically bound to a message cannot be removed through the pending-upload endpoint.

## Server storage and authorization

`encrypted_private_attachments` stores only:

- attachment UUID;
- uploader Account UUID;
- bound private-message UUID;
- random server storage name;
- ciphertext size;
- ciphertext SHA-256;
- lifecycle timestamps.

Ciphertext files live under a private storage root (`E2EE_ATTACHMENT_STORAGE_ROOT`, default `private_uploads/e2ee`). That directory is not mounted under the public `/uploads` static path.

Before the attachment is bound to a message, only its uploader may download or delete it. After binding, only the sender or receiver of the corresponding private message may download the ciphertext. Download responses use `application/octet-stream`, `nosniff` and `Cache-Control: private, no-store`.

`POST /crypto/v1/messages` accepts an optional `attachment_uid`. Binding the pending ciphertext row to the new E2EE message happens in the same database transaction as the private-message and per-device envelope persistence. The uploader must match the authenticated sender.

## Rendering

After the Messenger envelope is decrypted, the browser obtains the private attachment descriptor. Media rendering is lazy:

1. fetch authorized ciphertext;
2. verify SHA-256;
3. decrypt AES-256-GCM locally;
4. verify the expected plaintext size;
5. create an in-memory `blob:` URL using the decrypted MIME type;
6. pass that URL to the existing image/video/audio/voice/file UI.

The content key never needs to be uploaded outside the E2EE envelope.

## Compatibility and downgrade policy

If the peer has registered cryptographic devices, Messenger media uses encrypted attachment delivery. A cryptographic/upload/decryption setup failure does not silently resend the same file through the legacy plaintext/data-URL transport.

Legacy media delivery remains available only when the peer has no registered crypto devices, matching the text E2EE rollout policy.

When multiple files are selected in one composer action, v1 sends them as separate encrypted private messages. This avoids inventing a server-visible manifest and keeps one opaque blob bound to one E2EE message.

## Privacy consequences

Server-side transcription, thumbnail generation, MIME inspection and content moderation cannot run on E2EE attachment plaintext. For encrypted voice/audio/video this means no server transcription is requested. Future Trust & Safety evidence must remain explicit and consent-driven: a reporting client may choose to attach decrypted evidence, but routine server-side decryption is not part of this protocol.

## Storage retention and garbage collection

`python -m workers.e2ee_attachment_retention` is the bounded maintenance worker for private ciphertext storage.

It has two independent safety windows:

- `E2EE_ATTACHMENT_PENDING_RETENTION_HOURS` (default `24`) controls when an upload that was never bound to a private message becomes eligible for deletion;
- `E2EE_ATTACHMENT_ORPHAN_GRACE_HOURS` (default `24`) controls when a ciphertext file with no database row becomes eligible for orphan cleanup;
- `E2EE_ATTACHMENT_RETENTION_BATCH_SIZE` (default `100`, bounded to `1000`) limits work per cycle.

Bound attachments (`message_uid IS NOT NULL`) are not selected by the pending-upload cleanup. For stale pending uploads the worker commits database-row deletion first, then removes the private file. If that filesystem unlink fails, the file has no database reference and a later orphan pass can retry it.

The orphan pass only considers storage names generated by PubChat (`32 lowercase hex characters + .bin`), ignores symlinks and unrelated files, checks database references again before unlinking, and applies its own grace period. This prevents the cleanup job from becoming a generic recursive file deleter.

A systemd oneshot/timer pair is provided as `pubchat-e2ee-attachment-retention.service` and `.timer`; the timer runs every six hours with jitter. Install it with `ops/install-e2ee-attachment-retention-worker.sh`. A manual preview is available through `python -m workers.e2ee_attachment_retention --dry-run`.

## Follow-up work

The ciphertext lifecycle/GC blocker is implemented. Remaining security increments are stronger device verification UX (including QR comparison/key-transparency groundwork), long-lived session/re-key recovery testing, and final production E2EE/media validation.
