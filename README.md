# PubChat

PubChat — SPA-приложение для свободного общения и живых тематических сообществ. Пользователь создаёт Persona, входит в Living Spaces, общается в realtime, участвует в событиях и активностях, строит социальные связи и управляет приватностью.

Проект не является копией Galaxy: PubChat развивает собственную концепцию без покупки социального влияния и без тюремной терминологии.

## Статус

Release candidate текущей ветки: `0.6.30-alpha.1` — PostgreSQL pool observability. Последний выпущенный `main` checkpoint — `0.6.29-alpha.1`.

Текущая development-линия: `0.6.x-alpha` — Pre-beta hardening продолжается.

Stage 6 уже закрепил PostgreSQL 16 migration/integration/recovery baseline, Redis 7.2 distributed realtime, restart/recovery и real Sentinel master-promotion baseline, real multi-process Uvicorn/WebSocket rehearsal с rolling restart, bounded per-socket backpressure, message-notification delivery policy с distributed active-context suppression, durable unread-Messenger email delivery и standards-based Web Push/PWA Messenger delivery. Production backend запускается за постоянным systemd-owned listener, routine deploy меняет workers rolling reload без намеренного `502` окна, а frontend публикуется staged/asset-first.

Trust & Safety checkpoint `0.6.10-alpha.1` добавил отдельный platform report/triage/evidence контур, Account-level иерархию moderation authority, capability restrictions с server-side enforcement, target-visible reason/scope/expiry и независимый appeal flow. `0.6.11-alpha.1` завершил full `account.access` suspension: platform-only sanction отзывает существующие sessions, блокирует обычные HTTP/realtime surfaces по durable PostgreSQL restriction, отключает уже открытые WebSocket connections и оставляет затронутому Account только ограниченный Safety/appeal/logout контур. `0.6.12-alpha.1` разделил queue/manage, restriction issue/revoke и appeal-review powers отдельными permissions. `0.6.13-alpha.1` добавляет provider-neutral AI-copilot: privacy-minimal advisory assessment, bounded provider budget и human outcome tracking без права AI применять санкции. `0.6.14-alpha.1` добавляет durable behavioral abuse signals для rate-limit pressure, массовых DM-контактов и invite spam. `0.6.15-alpha.1` добавляет reversible human-only reported-media moderation. `0.6.16-alpha.1` добавляет aggregate operations metrics, incident rehearsal и строго ограниченные protective holds, которые выключены по умолчанию и требуют повторных high/critical server-owned signals. `0.6.17-alpha.1` добавляет bounded retention/expiry private moderation media с report/appeal safety gates, metadata scrub и отдельным scheduled worker. `0.6.18-alpha.1` добавляет shadow calibration, explicit human labels и fail-closed enablement gate для protective holds, а также preflight срока хранения backup/snapshot copies. `0.6.19-alpha.1` добавляет privacy-safe observability для email/Web Push delivery: агрегированные backlog/retry/failure metrics, admin-only operational endpoint, machine-readable health CLI и structured worker logs без пользовательских идентификаторов, адресов, push endpoints или текста сообщений. `0.6.20-alpha.1` закрепляет same-origin `/api`, explicit CSRF cookie+header proof, audit-clean production dependencies и реальный Playwright gate в Chromium/Firefox/WebKit/mobile. `0.6.21-alpha.1` добавляет единый motion/loading contract: плавные route/modal/popover transitions, delayed navigation progress, skeleton/error/retry состояния и явный pending feedback без искусственного замедления. `0.6.21-alpha.2` исправляет mobile blank-content regression вокруг RouterView transition и делает JWT session issuance уникальным через `jti`. `0.6.22-alpha.1` делает Space `member_limit` атомарным при concurrent join/invite/approval и исправляет UUID lookup путей Space service. `0.6.22-alpha.2` стабилизирует SPA-вход в комнату без reload и приводит mobile room shell к реальному `100dvh` без лишнего document scroll. `0.6.23-alpha.1` добавляет IANA timezone storage и сохраняет локальное wall-clock время recurring Activities через DST. `0.6.24-alpha.1`–`0.6.26-alpha.1` расширяют organic discovery candidate generation, query profiling и large-pool privacy/block regression. `0.6.27-alpha.1` добавляет Redis pool utilization/headroom observability и bounded realtime capacity profile. `0.6.28-alpha.1` закрывает upload/media security baseline: strict allowlist, byte/signature validation, atomic writes, Redis byte-rate budget и безопасные response headers. `0.6.29-alpha.1` разделяет user-facing и moderator-only moderation projections, чтобы жалобы/ограничения не раскрывали лишние Account↔Persona связи, moderator IDs и внутреннюю taxonomy. `0.6.30-alpha.1` добавляет per-process PostgreSQL pool capacity/headroom observability с явной multi-worker aggregation boundary.

`0.6.12-alpha.1` разделяет platform moderation access и punitive authority: выдача ограничений, снятие ограничений и review апелляций получают отдельные permissions. Обычный moderator может работать с временными capability restrictions только в пределах своей authority, но permanent sanctions и `account.access` остаются elevated-действиями. Снятие санкции дополнительно требует authority не ниже authority исходного решения, поэтому moderator не может отменить санкцию, выданную admin.

AI moderation зафиксирован как copilot: он может помогать triage, evidence summary и рекомендациями, но не является источником punitive authority. Human authority path, AI assessment, behavioral signals, reported-media workflow, operations metrics, incident rehearsal, private-evidence retention/expiry и tooling для shadow calibration уже реализованы. Protective holds остаются default-off: реальный enforce разрешается только после достаточной human-reviewed shadow выборки и отдельного operational approval.

Message delivery различает online presence и активный conversation/Space: лишний toast/sound подавляется, если пользователь уже смотрит тот же context. Offline external re-engagement разрешён только для Messenger по opt-in. Для давно отсутствующего Account email worker создаёт агрегированное privacy-safe напоминание по durable ledger/cooldown/retry contract, а Web Push может доставить privacy-minimal уведомление на явно подписанное устройство. Space chat по-прежнему не создаёт background notification pressure отсутствующему Account.

До beta всё ещё нужно накопить реальную human-reviewed shadow выборку для protective holds и подтвердить фактический provider backup/snapshot lifecycle, а также завершить rehearsal на anonymized production-like snapshot, broader HTTP/realtime/Redis/PostgreSQL/provider observability, malware/CDR policy for currently unsupported risky document/archive formats, accessibility и реальный iOS/iPadOS installed-PWA/device gate. Параллельно формализуются cost model и monetization boundaries, чтобы infrastructure/moderation не зависели от бессрочного ручного финансирования.

Канонический номер версии находится в `VERSION`, история выпусков — в `CHANGELOG.md`.

## Репозитории и нативные клиенты

- **Основная система (backend + веб-клиент):** [cyrox007/chat](https://github.com/cyrox007/chat), ветка `main` — текущее имя репозитория.
- **Android-клиент:** [cyrox007/PubChat-Android](https://github.com/cyrox007/PubChat-Android), ветка `master`; нативная разработка продолжается, до beta необходимы тесты на устройствах.
- **Планируемое имя основного репозитория:** `cyrox007/PubChat` (пока не переименован). Старый URL `PubChat` в данный момент ведёт к Android-репозиторию; не используйте его для клонирования backend.

Подробности, контракт WebRTC/FCM и инструкции на случай переименования: [`docs/client-repositories.md`](docs/client-repositories.md).

## Документация

Полный индекс: [`docs/README.md`](docs/README.md).

Основные документы:

- [`docs/installation.md`](docs/installation.md) — установка и первый запуск;
- [`docs/system-requirements.md`](docs/system-requirements.md) — системные требования;
- [`docs/user-guide.md`](docs/user-guide.md) — функции и пользовательские сценарии;
- [`docs/architecture.md`](docs/architecture.md) — архитектура;
- [`docs/api-and-realtime.md`](docs/api-and-realtime.md) — HTTP API и WebSocket;
- [`docs/security-and-privacy.md`](docs/security-and-privacy.md) — security/privacy model;
- [`docs/development.md`](docs/development.md) — разработка, миграции, тесты и CI;
- [`docs/operations.md`](docs/operations.md) — эксплуатация и background workers;
- [`docs/production-deploy-v1.md`](docs/production-deploy-v1.md) — persistent listener, staged SPA publish и health-gated rolling deploy;
- [`docs/message-notification-delivery-v1.md`](docs/message-notification-delivery-v1.md) — online/offline message routing, active context и external delivery policy;
- [`docs/message-email-delivery-v1.md`](docs/message-email-delivery-v1.md) — durable unread-Messenger email queue/provider/retry/systemd contract;
- [`docs/web-push-delivery-v1.md`](docs/web-push-delivery-v1.md) — per-device Web Push/VAPID/service-worker/provider/privacy contract;
- [`docs/external-delivery-observability-v1.md`](docs/external-delivery-observability-v1.md) — aggregate email/Web Push backlog/failure health, structured logs и privacy boundaries;
- [`docs/discovery-performance-v1.md`](docs/discovery-performance-v1.md) — discovery query-budget/latency profiling и operational CLI;
- [`docs/space-capacity-concurrency-v1.md`](docs/space-capacity-concurrency-v1.md) — atomic Space member-limit admission under concurrent joins/invites/approvals;
- [`docs/trust-safety-v1.md`](docs/trust-safety-v1.md) — hierarchical platform moderation, capability restrictions, enforcement/appeals и AI-copilot boundaries;
- [`docs/trust-safety-incident-rehearsal-v1.md`](docs/trust-safety-incident-rehearsal-v1.md) — moderation incident matrix, protective-hold safety gates и beta enablement boundary;
- [`docs/protective-hold-calibration-v1.md`](docs/protective-hold-calibration-v1.md) — off/shadow/enforce, human labels, calibration metrics и fail-closed rollout;
- [`docs/moderation-media-retention-v1.md`](docs/moderation-media-retention-v1.md) — private moderation evidence retention, expiry, worker и storage-boundary contract;
- [`docs/browser-compatibility-v1.md`](docs/browser-compatibility-v1.md) — browser launch matrix и Safari registration audit;
- [`docs/prebeta-hardening-v1.md`](docs/prebeta-hardening-v1.md) — Stage 6 PostgreSQL/migration hardening baseline;
- [`docs/database-recovery-v1.md`](docs/database-recovery-v1.md) — PostgreSQL backup/restore contract;
- [`docs/redis-realtime-integration-v1.md`](docs/redis-realtime-integration-v1.md) — Redis distributed realtime baseline;
- [`docs/redis-recovery-v1.md`](docs/redis-recovery-v1.md) — Redis restart/recovery contract;
- [`docs/redis-failover-v1.md`](docs/redis-failover-v1.md) — Redis Sentinel topology, promotion и failover recovery contract;
- [`docs/realtime-multiprocess-v1.md`](docs/realtime-multiprocess-v1.md) — real Uvicorn multi-process / rolling-restart contract;
- [`docs/realtime-backpressure-v1.md`](docs/realtime-backpressure-v1.md) — bounded per-socket outbound queues и slow-consumer isolation;
- [`docs/web-application-maturity-v1.md`](docs/web-application-maturity-v1.md) — PWA/offline shell и client lifecycle;
- [`docs/troubleshooting.md`](docs/troubleshooting.md) — типовые проблемы;
- [`docs/roadmap.md`](docs/roadmap.md) — актуальная дорожная карта;
- [`CHANGELOG.md`](CHANGELOG.md) — история версий.

## Технологии

Backend: Python 3.12, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16 CI baseline, Redis 7.2 CI baseline, WebSocket, Web Push/VAPID.

Frontend: Vue 3 SPA/PWA, Vite, Vue Router, Vuex, Axios, Service Worker/Push API.

SPA — основной веб-клиент; отдельный [Android-клиент](https://github.com/cyrox007/PubChat-Android) уже разрабатывается поверх общего API/realtime. Клиент iOS пока не создан.

## Ключевые правила

- `Account != Persona`.
- Reputation/achievements не дают permissions.
- Space moderator не является platform moderator.
- Platform moderation authority определяется server-side RBAC + explicit authority hierarchy; actor не может ограничить Account с равным или более высоким authority.
- Доступ к moderator queue (`moderation.platform.manage`) не равен праву применить санкцию: issue, revoke и appeal review имеют отдельные server-side permissions.
- Platform sanctions ограничивают конкретные capabilities и считаются работающими только там, где есть реальный server-side enforcement point.
- Temporary restriction требует явного issue permission; permanent sanctions требуют повышенного permission; `account.access` — отдельная elevated capability, platform-only и требует полного suspension enforcement.
- Прямое снятие санкции требует revoke permission, authority выше target и authority не ниже authority исходного actor; permanent/`account.access` сохраняют свои elevated permission checks.
- Appeal reviewer должен иметь отдельный appeal-review permission и authority не ниже authority исходного moderation action; independent review предпочтителен и проверяется server-side.
- `account.access` отзывает существующие sessions, блокирует обычный HTTP/realtime доступ и сохраняет только минимальный Safety/appeal/logout путь; старые sessions не восстанавливаются после revoke.
- AI moderation — copilot, а не самостоятельный punitive authority в beta baseline.
- Деньги не покупают trust и moderation power.
- Gifts/support не являются рейтингом и не влияют на discovery/authority.
- Organic discovery сначала применяет privacy/eligibility/moderation eligibility, а затем ranking.
- Числовой discovery score не является публичным API и не показывается пользователю.
- PostgreSQL — источник истины; Redis — ephemeral realtime слой.
- Production realtime не должен молча переходить в process-local fallback.
- Redis outage/failover должен быть видимым, а recovery — происходить без обязательного process restart.
- Direct `REDIS_URL` остаётся поддерживаемым; production HA может использовать Redis Sentinel без изменения realtime domain contract.
- Ticket/presence/rate-limit/idempotency/pub-sub semantics проверяются на настоящем Redis при `DEBUG=False`.
- Sentinel promotion проверяется на реальных Redis master/replica/Sentinel process, включая PubSub recovery и bounded concurrency после promotion.
- Multi-process WebSocket/rolling-restart semantics проверяются на реальных Uvicorn process в CI.
- Production listener принадлежит systemd socket unit и не должен исчезать при routine application deploy/restart.
- Routine backend deploy использует rolling worker reload; frontend build публикуется только после успешной staged сборки.
- Realtime fan-out не ждёт медленный socket write: каждый WebSocket имеет bounded outbound queue, а slow consumer изолированно отключается.
- Active context используется только для notification UX и никогда не расширяет/сужает message authorization.
- Offline external message re-engagement относится только к Messenger и требует opt-in; Space chat не создаёт фоновый spam отсутствующему Account.
- Durable external delivery state хранится в PostgreSQL; destination email и private message text не сохраняются в delivery ledger.
- Email и Web Push workers запускаются внешним scheduler/systemd timer и не живут внутри FastAPI web-worker lifecycle.
- Web Push payload не содержит private message body/sender identity, а VAPID private key остаётся backend-only.
- Browser notification permission запрашивается только после явного user gesture; logout/session teardown отвязывает local push subscription best-effort.
- Clean migration correctness проверяется на реальной PostgreSQL в CI; `create_all()` не заменяет Alembic rehearsal.
- Backup не считается рабочим, пока restore не проверен отдельной БД, schema-drift gate и semantic data assertions.
- Synthetic legacy/recovery fixtures не заменяют rehearsal на production-like snapshot.
- Access JWT браузера хранится только в памяти; долговременная сессия — HttpOnly refresh-cookie.
- Credentials не передаются в WebSocket URL.
- PWA service worker кэширует только shell/static assets и не является хранилищем auth/private API data.
- Standalone backend processes явно инициализируют ORM model registry.
- Activity reminders остаются opt-in; external email/Web Push delivery добавляется отдельными adapters.
- Creator support — бесплатные internal cosmetic gestures; реальные payments требуют отдельного financial/security review.


### Stage 6.8 checkpoint 6 — Reported media moderation ✅ `0.6.15-alpha.1`
- reported local attachments can be quarantined out of public `/uploads`, restored, or removed from public delivery;
- private evidence paths are server-only and retention keeps the evidence copy until a dedicated deletion policy applies;
- every action requires report claim ownership, explicit media permission and moderation authority over the target Account;
- moderator UI exposes deliberate human controls; AI and automation cannot perform punitive media actions.

### Incoming Android call wakeup (v1)

After a validated `call_offer`, the server saves a single account-scoped SDP offer for 60 seconds under Redis key `pubchat:calls:pending:v1:{account_uid}`. Authenticated `GET /calls/v1/pending-offer` returns that account's current offer; clients must reconnect to ticket-authenticated `/ws/v2/calls` and ask the user before answering. FCM call alert is best-effort and contains **no SDP, ICE, names or message content**. A sender may still cancel a call before the push is seen. Pending offers are cleared on answer/end/decline when possible and expire automatically. Server needs Redis and FCM credentials for recovery+wakeup.
