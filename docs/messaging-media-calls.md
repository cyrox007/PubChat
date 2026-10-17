# Messaging media, transcription and calls

PubChat uses one media/message contract for Spaces and Messenger. Voice notes and video messages are rendered by PubChat components rather than browser-native controls.

## Speech-to-text

Voice, audio and video messages are discovered by `backend/workers/media_transcription.py`. Jobs are durable in `media_transcription_jobs`; user media remains usable when the STT provider is unavailable.

Configure an internal/provider adapter through `TRANSCRIPTION_*`. The adapter accepts a JSON envelope containing `task=pubchat_media_transcription`, `schema_version=v1`, `model`, `media_url`, `surface` and `message_uid`, and returns `text`, optional `language`, and optional timestamped `segments`.

Run the worker repeatedly from the deployment scheduler, for example once per minute. It is safe to run concurrent workers because jobs are selected with `FOR UPDATE SKIP LOCKED`.

## WebRTC calls

Signaling uses `/ws/v2/calls`; media is WebRTC and is not proxied through the PubChat API. `messenger.send` restrictions and DM privacy/block policy also apply to calls.

The media channel uses browser WebRTC DTLS-SRTP. PubChat's signaling and TURN servers do not receive decoded microphone/camera media. A TURN relay forwards encrypted WebRTC packets and does not terminate the peer DTLS-SRTP session.

### Security claim for 1.0

The call security contract is explicit and deliberately narrower than Messenger message E2EE:

- `media_transport=webrtc-dtls-srtp`;
- `media_encrypted=true`;
- `signaling_e2ee=false`;
- `device_identity_bound=false`;
- `verified_application_e2ee=false`;
- `claim=transport-encrypted-unverified`.

This means WebRTC encrypts peer media in transit, but PubChat does **not** claim that the WebRTC DTLS fingerprint is cryptographically bound to the verified PubChat Account/device identity. SDP fingerprints and ICE candidates are relayed through PubChat signaling, so the signaling service still participates in peer setup.

The call UI exposes this distinction instead of showing a generic lock as if it meant verified application E2EE.

### Device-directory continuity before media capture

Outgoing call setup and incoming call acceptance both run the same `CryptoService.accountDevices()` boundary used by Messenger E2EE before requesting camera/microphone access.

For an E2EE conversation this validates the locally remembered device-directory checkpoint and any required append-only history continuity. A rollback, same-sequence fork or broken history chain fails closed and the call is not started/accepted. The incoming side returns the allow-listed `security_unavailable` decline reason.

For a plaintext conversation the directory continuity layer is marked not applicable. The call remains ordinary WebRTC DTLS-SRTP and is not promoted to verified E2EE.

This continuity check protects against proceeding through a device-directory state that the client already considers inconsistent. It still does **not** bind the WebRTC DTLS certificate/fingerprint to a specific verified E2EE device. Full verified call E2EE remains a future protocol layer, not a 1.0 claim.

### ICE/TURN credentials

Clients fetch ICE configuration from authenticated `GET /calls/v1/ice-config`. Do not put long-lived TURN usernames/passwords in `VITE_*` configuration: Vite build-time variables are public browser assets.

Production settings:

- `CALL_ICE_STUN_URLS` — comma-separated STUN URLs.
- `CALL_ICE_TURN_URLS` — comma-separated `turn:` / `turns:` URLs for coturn.
- `CALL_ICE_TURN_SHARED_SECRET` — server-only coturn `static-auth-secret`; never expose it to the frontend.
- `CALL_ICE_CREDENTIAL_TTL_SECONDS` — short-lived TURN credential TTL, default 3600 seconds.
- `CALL_ICE_PRIVACY_MODE=true` — forces `iceTransportPolicy=relay`. This prevents direct host/server-reflexive peer candidates from being used and therefore avoids exposing each participant's direct IP candidate to the other participant. All media then traverses TURN, still protected by peer WebRTC DTLS-SRTP.

The backend derives time-limited, account-scoped TURN REST credentials. TURN URLs without a sufficiently strong shared secret are rejected by the ICE endpoint.

For local development a STUN-only configuration is usually sufficient. Production should deploy its own TURN service for reliability across carrier NAT, enterprise networks and restrictive mobile networks. Privacy-sensitive production can enable relay-only mode after TURN capacity is provisioned.

### Signaling privacy / abuse controls

Call signaling is deliberately minimal: only WebRTC SDP type/body, the supported ICE candidate fields, call UUID, call mode and allow-listed end reasons are forwarded. Arbitrary client metadata is discarded. SDP/ICE payloads are size-bounded and call signaling has a separate distributed realtime rate limit; repeated offers have a stricter limit to reduce call-spam abuse.

Account-level access restrictions disconnect Messenger, Room and call sockets.

## Message actions

`/messages/v2` provides shared edit, soft-delete, reactions and forwarding operations for both `room` and `messenger` surfaces. Realtime updates reuse the existing message UID so connected clients replace the current message rather than creating duplicates.

## Rollout

1. Apply database migrations through the current Alembic head.
2. Configure an STT provider, then schedule the transcription worker.
3. Deploy coturn with `use-auth-secret`/`static-auth-secret`, configure `CALL_ICE_TURN_URLS` and `CALL_ICE_TURN_SHARED_SECRET`, and remove any old static TURN credentials from frontend deployment variables.
4. Decide whether production uses normal ICE (`CALL_ICE_PRIVACY_MODE=false`) or relay-only privacy mode after sizing TURN capacity.
5. Validate audio/video recording permissions on Android Chrome, iOS Safari and desktop Chromium/Firefox.
6. Validate calling across Wi-Fi ↔ cellular and two different NATs, not only on the same LAN.
7. Keep the 1.0 product claim precise: WebRTC media is DTLS-SRTP encrypted; verified application-level E2EE for calls is not implemented until the call handshake is bound to verified PubChat device identity.
