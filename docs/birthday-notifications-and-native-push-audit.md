# Birthday reminders + notification delivery audit (PubChat 0.7)

2026-10-18. Static repository audit; device delivery and production credentials
**were not verified on physical phones or the live server**.

## Birthday policy (implemented in this slice)

The existing `personas.date_of_birth` column stores a private complete date of birth.
It was previously not editable through Identity v2. This slice adds a private
primary-Persona edit field; the full date is returned only in **the owner's
Identity response**, never in public Persona projection, discovery or friend
list responses.

Two separate, **default-off** consents are required:

1. Birthday person: `privacy_settings.share_birthday_with_friends`. When
   revoked, previously generated birthday inbox rows are purged.
2. Recipient: `message_notification_preferences.friend_birthday_reminders`.

The server creates one in-app `friend_birthday` notification per friend per
UTC day. It requires a **mutual friend relationship**, both accounts active,
no Account-level block in either direction, and both consent flags true.
The notification mentions a name and birthday *today*, **never the birth
year or complete date**. It is stored in the normal `user_notifications`
inbox with a dedupe key, via the existing reminder worker and `/sync` API.
Leap-day birthdays use February 28 in non-leap years. The first slice uses
UTC day boundaries; per-user timezone/quiet hours need a separate opt-in
product design.

**No birthday background push is claimed.** Existing external push queues
deliver generic offline Messenger alerts only. Birthday reminders are
available in the shared in-app inbox; Android can read that inbox, Web
supports opt-in; iOS has no native inbox yet.

## Actual notification channels

| Platform | In-app inbox | Foreground UI/realtime | Background system push | Dependency |
| --- | --- | --- | --- | --- |
| Web SPA / PWA | Implemented | Native Web Notifications / app state | Web Push implemented, opt-in and VAPID/server worker required | Browser push service delivers subscription events |
| Android native | Implemented | Kotlin/Android app + WS | FCM HTTP v1 server adapter and Firebase client SDK are present | Google FCM and OS services; permission/token/server credentials required |
| Native iOS | Not implemented as of audit | SwiftUI base views only | APNs schema only, APNs client registration and provider worker not implemented | APNs and Apple signing/capability required |

PubChat owns its API, privacy filtering, message eligibility, durable delivery
ledger, retries and operations. There is **no OneSignal/Pusher SaaS** in
the shipping path. Android currently **does depend on the Firebase Messaging
client library**; Web delivery uses configured cryptographic VAPID and the
browser's native Push API. Purely replacing FCM/APNs with proprietary
WebSocket polling cannot reliably wake a force-closed/backgrounded app on
all Android/iOS devices, particularly during Doze or iOS process suspension.

Implementing an app's own notification renderer using native Android
`NotificationManager` / iOS `UNUserNotificationCenter` **does not remove**
FCM/APNs as background *remote* delivery transports. Local scheduled
notifications can work for already-known events but not reliably for new
server messages after the OS suspends the app. Android SDK-free remote
background delivery across all OEMs is not supported by the standard OS API.

## Verification status and release gate

Code/unit/CI validate API contracts and client builds. They do **not**
verify FCM project credentials, installed push timers, production VAPID
keys, OS notification permission or device token registration, live delivery,
Doze, iOS entitlement/signing, Safari installed-PWA mode, or click-through.

Before claiming complete push support:

- Web desktop Chrome/Firefox/Safari + installed iOS PWA: opt-in,
  denied permission, logout/unsubscribe, offline delivery/click.
- Android: 2+ physical devices, API 26+, one with aggressive battery
  optimization; token rotation, Wi-Fi/LTE, background/Doze/force-stop;
  direct FCM provider/OS behavior.
- iOS: implement native inbox and APNs token registration plus
  server APNs HTTP/2 provider; verify with a signed physical build.
  GitHub macOS iPhone Simulator compile alone cannot validate APNs delivery.
- All: invalid devices revoked, user preferences respected, no private
  message text or DOB leakage, reasonable retry/alerting and one inbox
  notification per dedupe key.

References within this repo: `docs/native-push-v1.md`,
`docs/web-push-delivery-v1.md`, `backend/components/notification/native_push.py`,
`backend/components/notification/web_push.py`.
