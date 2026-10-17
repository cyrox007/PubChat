# Native Push v1

PubChat owns native notification policy, device registrations, durable queueing, retries and observability. There is no OneSignal, Pusher or other push SaaS in this path.

## Android transport

Android delivery uses Firebase Cloud Messaging **HTTP v1 directly from the PubChat backend**. FCM is treated only as the Android operating-system delivery transport. PubChat does not use a third-party notification orchestration service and does not give an external service access to PubChat conversations.

The worker obtains an OAuth access token itself from the configured Google service-account credentials and posts directly to:

`https://fcm.googleapis.com/v1/projects/<project>/messages:send`

Configuration:

- `FCM_PROJECT_ID`
- `FCM_SERVICE_ACCOUNT_EMAIL`
- `FCM_SERVICE_ACCOUNT_PRIVATE_KEY` — PEM private key, server-only; `\\n` escaped newlines are accepted.
- `NATIVE_PUSH_DELIVERY_MAX_ATTEMPTS` — default 5.
- `NATIVE_PUSH_DELIVERY_RETRY_BASE_SECONDS` — default 60.
- `NATIVE_PUSH_DELIVERY_RETRY_MAX_SECONDS` — default 1800.
- `NATIVE_PUSH_DELIVERY_LEASE_SECONDS` — default 180.
- `NATIVE_PUSH_DELIVERY_BATCH_SIZE` — default 50.
- `NATIVE_PUSH_CONVERSATION_COOLDOWN_SECONDS` — default 90.
- `EXTERNAL_DELIVERY_NATIVE_PUSH_BACKLOG_ALERT_SECONDS` — default 300.

FCM credentials are optional at API startup. If they are absent, the native-push worker refuses delivery without affecting the web application, Web Push or email.

## Device registration

An authenticated native client owns a random stable `installation_uid` and registers its current OS push token:

- `GET /notifications/v1/native-push/config`
- `GET /notifications/v1/native-push/devices`
- `POST /notifications/v1/native-push/devices`
- `POST /notifications/v1/native-push/devices/remove`

Android v1 accepts `platform=android`, `provider=fcm`. The token is a private delivery credential. API list projections never return it; operations metrics never include it. Only its SHA-256 fingerprint is used for uniqueness.

A registration follows the most recently authenticated Account using that installation/token. This prevents a phone that signs out of Account A and signs into Account B from continuing to receive A's notifications after B registers the same installation. The native client must also call the remove endpoint during explicit logout before clearing its local session; removing/revoking the registration is idempotent.

Native Messenger push remains an explicit Account preference (`native_push_messenger`). The native app should enable it only after the user grants notification permission. Merely possessing a token does not silently opt an Account into external re-engagement.

## Durable delivery

Native push reuses `external_delivery_ledger` with channel `native_push`. The worker:

1. scans Accounts that both opted in and have an active native device;
2. derives a privacy-safe unread DM aggregate from durable message state;
3. inserts a deduplicated ledger row with a cooldown window;
4. claims due rows using a lease and `FOR UPDATE SKIP LOCKED`;
5. suppresses delivery if the Account is currently online;
6. retries transient FCM/network failures with bounded exponential backoff;
7. revokes tokens reported by FCM as unregistered/invalid;
8. records only provider message ID/failure class required for operations.

The systemd timer runs the worker every ~30 seconds. Multiple overlapping workers remain safe because durable claims are leased and row-locked.

## E2EE / privacy boundary

Native push is deliberately content-blind. Its Messenger payload is always generic:

- title: `Новое сообщение в PubChat`
- body: `У вас есть новое личное сообщение.`
- route: `/messenger`

The payload does **not** contain message plaintext, E2EE ciphertext, sender display name, attachment filename, media metadata, Space/private-chat content, safety numbers or cryptographic key material. The worker derives only unread count/state from the database and never decrypts an E2EE envelope.

This same rule applies to both legacy/plaintext and E2EE DM rows, so enabling native notifications does not weaken Messenger E2EE.

## iOS

The registration schema already reserves `platform=ios`, `provider=apns`, but APNs transport is intentionally not claimed as implemented in v1. The worker provider boundary is designed so a direct APNs adapter can be added without changing Account preferences, device-registration ownership, durable ledger semantics or notification privacy.

## Server rollout

1. Apply Alembic migration `r6g2j0f55006`.
2. Create a least-privilege Google service account allowed to send FCM messages for the PubChat Android project.
3. Configure the three `FCM_*` values in `/home/projects/pubchat/backend/.env`.
4. Install `ops/systemd/pubchat-native-push.service` and `.timer` under `/etc/systemd/system/`.
5. `systemctl daemon-reload`.
6. `systemctl enable --now pubchat-native-push.timer`.
7. Check `systemctl status pubchat-native-push.timer` and `journalctl -u pubchat-native-push.service`.
8. Register an Android installation through the API and explicitly enable `native_push_messenger` after OS notification permission is granted.
9. Verify `/admin/operations` reports the `native_push` ledger health without exposing tokens or message content.
