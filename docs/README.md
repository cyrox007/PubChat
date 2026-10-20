# Документация PubChat

Этот каталог — единая точка входа в документацию проекта. Документы разделены по назначению: продукт, пользовательские сценарии, установка, архитектура, разработка и эксплуатация.

## Начать работу

1. [`system-requirements.md`](system-requirements.md) — что требуется для запуска.
2. [`installation.md`](installation.md) — установка backend/frontend и первый старт.
3. [`user-guide.md`](user-guide.md) — что умеет PubChat и как пользоваться функциями.
4. [`troubleshooting.md`](troubleshooting.md) — типовые проблемы.

## О продукте

- [`product-concept.md`](product-concept.md) — позиционирование и продуктовые инварианты.
- [`roadmap.md`](roadmap.md) — последовательность продуктовых этапов.
- [`social-content-media-platform-v1.md`](social-content-media-platform-v1.md) — **план** личной стены/ленты, текстовых и фото-постов, граффити, видео/музыки, Stories/Reels и S3-хранилища с персональными Account-квотами; [эпик #134](https://github.com/cyrox007/PubChat/issues/134). Не считать готовой функцией.
- [`unified-content-moderation-v2.md`](unified-content-moderation-v2.md) — **план** управляемой цензуры слов/вариаций, проверки всех типов контента, жалоб с ограниченным контекстом, добровольного E2EE evidence и AI triage; [Epic #144](https://github.com/cyrox007/PubChat/issues/144).
- [`cross-client-delivery-status.md`](cross-client-delivery-status.md) — **проверенное состояние пользовательских сценариев Web / Android / iOS, CI/device QA и следующие незакрытые задачи**. Сверять перед каждой реализацией.
- [`../CHANGELOG.md`](../CHANGELOG.md) — история выпущенных версий.
- [`versioning.md`](versioning.md) — политика alpha/beta/stable.
- [`versioning-quick-reference.md`](versioning-quick-reference.md) — краткий статус версии.
- [`ui-ux-kit.md`](ui-ux-kit.md) — основная дизайн-система и UX-правила.
- [`ui-ux-notifications.md`](ui-ux-notifications.md) — notification/reminder UX extension.
- [`ui-ux-discovery.md`](ui-ux-discovery.md) — explainable organic discovery UX rules.
- [`ui-ux-pwa.md`](ui-ux-pwa.md) — install/update/offline UX extension.

## Клиенты и репозитории

- [`client-repositories.md`](client-repositories.md) — фактические адреса GitHub, границы backend/Android, WebRTC и FCM contracts, beta gate и процедура будущего переименования.
- [PubChat Android README](https://github.com/cyrox007/PubChat-Android/blob/master/README.md) — установка, реализованный функционал и ограничения Android-клиента.

## Для разработчика

- [`architecture.md`](architecture.md) — модули, домены, данные и границы ответственности.
- [`client-architecture.md`](client-architecture.md) — SPA-first/API-first модель клиента.
- [`api-and-realtime.md`](api-and-realtime.md) — HTTP API, auth/session и WebSocket v2.
- [`security-and-privacy.md`](security-and-privacy.md) — security model и privacy boundaries.
- [`moderation-privacy-v1.md`](moderation-privacy-v1.md) — reporter/target vs moderator-only moderation projection boundaries (`0.6.29-alpha.1`).
- [`upload-media-security-v1.md`](upload-media-security-v1.md) — server allowlist, byte/signature validation, storage/rate-limit/response-header contract (`0.6.28-alpha.1`).
- [`development.md`](development.md) — ветки, миграции, тесты и CI.
- [`operations.md`](operations.md) — production-конфигурация и эксплуатационные ограничения.
- [`postgres-pool-observability-v1.md`](postgres-pool-observability-v1.md) — per-process SQLAlchemy pool capacity/health и multi-worker aggregation boundary (`0.6.30-alpha.1`).
- [`production-deploy-v1.md`](production-deploy-v1.md) — persistent listener, staged SPA publish и health-gated rolling production deploy.
- [`message-notification-delivery-v1.md`](message-notification-delivery-v1.md) — message preferences, online/offline routing, active-context suppression и external channel policy.
- [`message-email-delivery-v1.md`](message-email-delivery-v1.md) — durable unread-Messenger email ledger/provider/retry/systemd contract (`0.6.8-alpha.1`).
- [`web-push-delivery-v1.md`](web-push-delivery-v1.md) — per-device Web Push/VAPID/service-worker/provider/privacy contract (`0.6.9-alpha.1`).
- [`external-delivery-observability-v1.md`](external-delivery-observability-v1.md) — privacy-safe email/Web Push backlog/failure metrics, health CLI и structured-log boundary (`0.6.19-alpha.1`).
- [`browser-compatibility-v1.md`](browser-compatibility-v1.md) — same-origin/CSRF contract и Chromium/Firefox/WebKit/mobile launch gate (`0.6.20-alpha.1`).
- [`space-capacity-concurrency-v1.md`](space-capacity-concurrency-v1.md) — atomic Space member-limit admission and PostgreSQL concurrency rehearsal (`0.6.22-alpha.1`).
- [`prebeta-hardening-v1.md`](prebeta-hardening-v1.md) — PostgreSQL/migration baseline (`0.6.0-alpha.1`).
- [`database-recovery-v1.md`](database-recovery-v1.md) — PostgreSQL backup/restore (`0.6.1-alpha.1`).
- [`redis-realtime-integration-v1.md`](redis-realtime-integration-v1.md) — Redis distributed realtime baseline (`0.6.2-alpha.1`).
- [`redis-recovery-v1.md`](redis-recovery-v1.md) — real Redis restart/outage recovery (`0.6.3-alpha.1`).
- [`realtime-multiprocess-v1.md`](realtime-multiprocess-v1.md) — real Uvicorn multi-process/rolling-restart baseline (`0.6.4-alpha.1`).
- [`realtime-backpressure-v1.md`](realtime-backpressure-v1.md) — bounded outbound queues и slow-consumer isolation (`0.6.5-alpha.1`).
- [`redis-failover-v1.md`](redis-failover-v1.md) — Redis Sentinel topology/promotion/capacity baseline (`0.6.6-alpha.1`).
- [`release-checklist.md`](release-checklist.md) — release gate.

## Доменные документы

- [`identity-v2.md`](identity-v2.md) — Account/Persona/Credential/Session/Privacy.
- [`realtime-v2.md`](realtime-v2.md) — tickets, Redis pub/sub, presence, reconnect.
- [`trust-safety-v1.md`](trust-safety-v1.md) — platform report intake, иерархия ролей, capability restrictions, runtime enforcement, audit/appeals и AI-copilot boundaries (`0.6.10-alpha.1` foundation; `0.6.11-alpha.1` full `account.access`; `0.6.12-alpha.1` permission/hierarchy hardening; `0.6.13-alpha.1` provider-neutral AI copilot; `0.6.14-alpha.1` behavioral anti-spam/raid signals; `0.6.15-alpha.1` reversible reported-media moderation; `0.6.16-alpha.1` operations/protective-hold baseline; `0.6.17-alpha.1` private media retention/expiry; `0.6.18-alpha.1` protective-hold shadow calibration/storage lifecycle gate).
- [`product-identity-v1.md`](product-identity-v1.md) — Persona/Space appearance и recurring Activities.
- [`social-engagement-v2.md`](social-engagement-v2.md) — earned achievements и Conversation Rounds.
- [`activity-occurrences-v1.md`](activity-occurrences-v1.md) — occurrences/reminders/inbox.
- [`creator-support-v1.md`](creator-support-v1.md) — cosmetic gifts/support.
- [`discovery-v1.md`](discovery-v1.md) — eligibility-first organic discovery; multi-source bounded candidate generation (`0.6.24-alpha.1`).
- [`discovery-performance-v1.md`](discovery-performance-v1.md) — query-count/latency profiling and load guard (`0.6.25-alpha.1`).
- [`web-application-maturity-v1.md`](web-application-maturity-v1.md) — PWA/offline shell и client lifecycle.

## Статус документов

`VERSION` и `CHANGELOG.md` — источник истины для выпущенного checkpoint. Активный development scope находится в `roadmap.md`.

Release candidate текущей ветки: `0.6.30-alpha.1`; последний выпущенный `main` checkpoint — `0.6.29-alpha.1` до финального exact-head CI и merge.

Текущая development-линия: `0.6.x-alpha`. `0.6.30-alpha.1` добавляет per-process PostgreSQL pool capacity/headroom observability с явной границей multi-worker aggregation.

- `trust-safety-incident-rehearsal-v1.md` — moderation incident matrix, protective-hold safeguards и beta enablement gate.

- [`moderation-media-retention-v1.md`](moderation-media-retention-v1.md) — bounded private moderation evidence retention, expiry worker, path/storage boundaries and backup caveats.

- [`protective-hold-calibration-v1.md`](protective-hold-calibration-v1.md) — off/shadow/enforce, human labels, per-signal-family FP gate и controlled rollout.
