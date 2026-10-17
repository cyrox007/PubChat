# Multi-device Account & Session lifecycle

PubChat treats **Account**, **auth device/session**, and **E2EE crypto device** as separate concepts.

## Identity model

- `Account` is the platform identity used for policy, trust, abuse history and global sanctions.
- `device_uid` is a non-secret, stable identifier for one browser profile/application installation. The web client stores a random UUID locally and sends it as `X-PubChat-Device-ID`.
- `IdentitySession.uid` is one authorization session on that device. Several sessions may belong to the same device.
- E2EE crypto devices remain a separate registry. Logging out does not silently delete a crypto identity or alter safety-number history.

The device UUID does **not** authenticate the caller. Account/session authorization still comes from signed tokens and the durable `identity_sessions` record.

## Token and revocation boundary

Modern Identity v2 access/refresh tokens contain:

- `sub`: Account UID;
- `sid`: IdentitySession UID;
- `did`: auth device UID.

Every authenticated HTTP request carrying `sid` re-checks that the durable session is active and not expired. A revoked session therefore stops working immediately instead of waiting for the access JWT lifetime.

Legacy tokens without `sid` remain temporarily compatible so old clients can migrate through refresh. A legacy refresh is upgraded to a session-bound token pair.

## Realtime / WebSocket semantics

Realtime tickets are issued by an authenticated HTTP request and bind the one-time ticket to its `sid` and `did`. WebSocket authentication consumes the ticket and re-checks that the referenced durable session is still active before accepting it.

Each concrete WebSocket stores Account/session/device routing metadata. Multiple sockets for the same Account are expected and supported:

- several physical devices;
- several browser profiles;
- several tabs from the same browser/device.

Account presence remains aggregated: the Account is online while **any** connection is alive. Closing/revoking one session does not mark the Account offline while another connection remains.

Messages addressed to an Account continue to fan out to all of its active Messenger sockets. Server/client idempotency keeps reconnect/replay from creating duplicate persisted messages.

## Session control

`GET /identity/v2/sessions` returns active devices with their sessions and identifies the current session/device.

The owner can:

- revoke one session: `DELETE /identity/v2/sessions/{session_uid}`;
- revoke every active session on one auth device: `DELETE /identity/v2/devices/{device_uid}`;
- revoke all sessions except the current one: `POST /identity/v2/sessions/revoke-others`;
- use normal logout to revoke the current refresh session.

After the durable database update, a `session_control` realtime event is published. Every worker closes only sockets whose Account plus session/device selector matches the event. If Redis is unavailable, the database revocation remains authoritative and subsequent HTTP/ticket authentication still fails closed.

## UI

Authenticated users can open **Устройства и сеансы** from the account menu. The screen shows active browser/device groups, individual sessions, current-session marking, recent activity and per-session/device revoke actions.

## Security boundary

Auth device IDs are pseudorandom routing/grouping identifiers, not trust signals and not moderation identities. Switching devices never creates a new Account, reputation, vote identity or sanction boundary. Device/session revocation is also distinct from E2EE crypto-device revocation.
