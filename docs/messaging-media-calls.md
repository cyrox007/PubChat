# Messaging media, transcription and calls

PubChat uses one media/message contract for Spaces and Messenger. Voice notes and video messages are rendered by PubChat components rather than browser-native controls.

## Speech-to-text

Voice, audio and video messages are discovered by `backend/workers/media_transcription.py`. Jobs are durable in `media_transcription_jobs`; user media remains usable when the STT provider is unavailable.

Configure an internal/provider adapter through `TRANSCRIPTION_*`. The adapter accepts a JSON envelope containing `task=pubchat_media_transcription`, `schema_version=v1`, `model`, `media_url`, `surface` and `message_uid`, and returns `text`, optional `language`, and optional timestamped `segments`.

Run the worker repeatedly from the deployment scheduler, for example once per minute. It is safe to run concurrent workers because jobs are selected with `FOR UPDATE SKIP LOCKED`.

## WebRTC calls

Signaling uses `/ws/v2/calls`; media is WebRTC and is not proxied through the PubChat API. `messenger.send` restrictions and DM privacy/block policy also apply to calls.

The media channel uses browser WebRTC DTLS-SRTP. PubChat's signaling and TURN servers do not receive decoded microphone/camera media. A TURN relay forwards encrypted WebRTC packets and does not terminate the peer DTLS-SRTP session.

This is **not yet the same security claim as verified application-level E2EE against a compromised signaling server**. SDP fingerprints and ICE candidates are currently relayed by PubChat signaling, so the server participates in peer setup and is not yet cryptographically excluded from identity verification. Do not label calls as "verified E2EE" until device cryptographic identity/key verification is implemented and bound to the call handshake.

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

1. Apply Alembic migration `m1b7e5a99001`.
2. Configure an STT provider, then schedule the transcription worker.
3. Deploy coturn with `use-auth-secret`/`static-auth-secret`, configure `CALL_ICE_TURN_URLS` and `CALL_ICE_TURN_SHARED_SECRET`, and remove any old static TURN credentials from frontend deployment variables.
4. Decide whether production uses normal ICE (`CALL_ICE_PRIVACY_MODE=false`) or relay-only privacy mode after sizing TURN capacity.
5. Validate audio/video recording permissions on Android Chrome, iOS Safari and desktop Chromium/Firefox.
6. Validate calling across Wi-Fi ↔ cellular and two different NATs, not only on the same LAN.
7. Do not advertise calls as verified E2EE until device identity and call-key/fingerprint verification are implemented.
