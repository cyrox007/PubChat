# Messaging media, transcription and calls

PubChat uses one media/message contract for Spaces and Messenger. Voice notes and video messages are rendered by PubChat components rather than browser-native controls.

## Speech-to-text

Voice, audio and video messages are discovered by `backend/workers/media_transcription.py`. Jobs are durable in `media_transcription_jobs`; user media remains usable when the STT provider is unavailable.

Configure an internal/provider adapter through `TRANSCRIPTION_*`. The adapter accepts a JSON envelope containing `task=pubchat_media_transcription`, `schema_version=v1`, `model`, `media_url`, `surface` and `message_uid`, and returns `text`, optional `language`, and optional timestamped `segments`.

Run the worker repeatedly from the deployment scheduler, for example once per minute. It is safe to run concurrent workers because jobs are selected with `FOR UPDATE SKIP LOCKED`.

## WebRTC calls

Signaling uses `/ws/v2/calls`; media is WebRTC and is not proxied through the PubChat API. `messenger.send` restrictions and DM privacy/block policy also apply to calls.

For local development, a public STUN server is sufficient for many network combinations. Production must configure `VITE_WEBRTC_ICE_SERVERS` with the deployment's STUN/TURN servers. TURN is required for reliable carrier-NAT, enterprise and restrictive mobile networks. Credentials belong in deployment secrets.

Account-level access restrictions disconnect Messenger, Room and call sockets.

## Message actions

`/messages/v2` provides shared edit, soft-delete, reactions and forwarding operations for both `room` and `messenger` surfaces. Realtime updates reuse the existing message UID so connected clients replace the current message rather than creating duplicates.

## Rollout

1. Apply Alembic migration `m1b7e5a99001`.
2. Configure an STT provider, then schedule the transcription worker.
3. Configure production TURN credentials before enabling calls broadly.
4. Validate audio/video recording permissions on Android Chrome, iOS Safari and desktop Chromium/Firefox.
5. Validate calling across Wi-Fi ↔ cellular and two different NATs, not only on the same LAN.
