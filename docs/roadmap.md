# Дорожная карта PubChat

## Трёхклиентная продуктовая линия (решение 18.10.2026)

PubChat развивается в трёх репозиториях: Web/backend
[`cyrox007/PubChat`](https://github.com/cyrox007/PubChat),
Android [`cyrox007/PubChat-Android`](https://github.com/cyrox007/PubChat-Android)
и iOS [`cyrox007/PubChat-iOS`](https://github.com/cyrox007/PubChat-iOS).

**Web = Android = iOS по пользовательским возможностям к 1.0.**
Один backend/API, одни решения по доступу, приватности, модерации и экономике,
единая сценарная проверка. Раннее завершение web-кода — не завершение общего эпика.

- **0.7 Social Core** — Account/Persona, социальные связи, intent и discovery,
  единое согласие на DM; старт нативного iOS, закрытие базовых пробелов Android.
- **0.8 Living Spaces** — Spaces, realtime и social loops, Activities, игры,
  повторное участие и память сообществ с функциональным паритетом.
- **0.9 Product Experience** — Safety Center, нативные push, звонки,
  достижения/репутация, поддержка и экономические функции с паритетом.
- **1.0 Release** — общая API/contract матрица, автотесты, реальные устройства
  Web/Android/iOS, безопасность, подписанные мобильные сборки и release gate.

Существующие `0.6.x-alpha` hardening-задачи ниже не отменяются:
это актуальная инфраструктурная база, на которой строится продуктовая линия.

## Текущий статус

Release candidate: **`0.6.30-alpha.1`**; last merged `main` checkpoint: **`0.6.29-alpha.1`**.

Current milestone: **`0.6.x-alpha`** — Pre-beta hardening продолжается.

Уже закреплены CI: PostgreSQL migration/recovery, Redis distributed/restart recovery, real Sentinel promotion, multi-process Uvicorn/WebSocket rolling restart, bounded backpressure, production deploy continuity, message notification policy с distributed active-context suppression, durable unread-Messenger email delivery, Web Push/PWA Messenger delivery, full `account.access` enforcement и fine-grained platform moderation permission boundaries.

Provider-neutral AI assessment / copilot, anti-spam/raid behavioral signals, reported-media moderation, operations metrics, incident rehearsal, private-evidence retention/expiry и shadow-calibration/storage-lifecycle gate уже закрыты отдельными checkpoints. Protective holds остаются default-off; следующий Trust & Safety operational task — **накопить human-reviewed shadow data и подтвердить фактический provider backup/snapshot lifecycle перед enforce**. External-delivery observability baseline уже закрывает ledger-side backlog/failure visibility. Browser/security checkpoint закрывает same-origin `/api`, explicit CSRF proof, dependency audit и Chromium/Firefox/WebKit/mobile auth-session matrix. Upload/media baseline теперь закрывает allowlist, byte/signature validation, atomic writes и media-rate limiting; дальше остаются broader HTTP/realtime/Redis/PostgreSQL/provider telemetry, malware/CDR policy для более широких типов, real-device PWA/accessibility gates и формализация unit economics/monetization boundaries.

Отдельно зафиксированы два обязательных launch workstream, которые раньше были недооценены: **production-grade moderation / Trust & Safety** и **устойчивая монетизация / unit economics**. PubChat не может считать наличие таблиц moderation готовой системой и не может рассчитывать, что инфраструктура, поддержка и Trust & Safety будут бесконечно финансироваться только энтузиазмом команды.

## Завершённые checkpoints

### Stage 1 — Foundation & Security ✅ `0.1.0-alpha.1`
Security baseline, server-side RBAC, legacy exposure fixes и CI.

### Stage 2 — Identity v2 ✅ `0.2.0-alpha.1`
Account/Persona/Credential/IdentitySession, privacy, relationships и Persona-first SPA shell.

### Stage 3 — Realtime v2 ✅ `0.3.0-alpha.1`
One-time WebSocket tickets, Redis pub/sub/presence, heartbeat/reconnect, rate limits/idempotency.

### Stage 4 — Living Spaces & Social Core ✅ `0.4.0-alpha.1`
Spaces/memberships/scoped roles, social graph, invitations, Rules/Events/History и moderation/appeals foundation.

### Stage 5.1–5.6 ✅ `0.5.0-alpha.1` → `0.5.5-alpha.1`
Product identity/Activities, earned engagement, occurrences/reminders, cosmetic support, organic discovery и installable PWA/external reminder-worker baseline.

### Stage 6 checkpoint 18 — Large-pool discovery privacy/block regression ✅ `0.6.26-alpha.1`
- 260+ Space fixture проверяет privacy/block semantics после насыщения candidate pool;
- blocked-owner public recommendation подавляется без membership, existing active membership сохраняется;
- private outsider Space не проходит canonical eligibility даже при recent/upcoming candidate signals;
- pending private membership не получает recent/upcoming live-context reasons/projection;
- response проверяется на отсутствие sensitive sentinel name/UID;
- privacy path остаётся внутри discovery query/latency budget.

### Stage 6 checkpoint 22 — PostgreSQL pool observability ✅ `0.6.30-alpha.1`
- SQLAlchemy pool size/overflow/timeout вынесены в bounded environment settings;
- admin-only runtime endpoint показывает privacy-safe checked-out/in, overflow, headroom, utilization и near-capacity health;
- метрика явно имеет `scope=current_process`: каждый Uvicorn worker владеет собственным pool;
- standalone CLI исключён как вводящий в заблуждение для live worker pools;
- capacity planning документирован как per-process capacity × worker count плюс другие PostgreSQL clients;
- functional exact-head CI #787 green до release/version sync.

### Stage 6 checkpoint 21 — Moderation privacy projections ✅ `0.6.29-alpha.1`
- reporter Trust & Safety history больше не выводит target Account UID/primary Persona, queue priority, moderator assignment или internal resolution code;
- Space report history не выполняет скрытую Account→primary-Persona корреляцию;
- target-facing platform restrictions содержат только scope/capability/public explanation/status/timing;
- moderator-only restriction view сохраняет report/actor/target/reason/origin для внутренних workflows;
- Safety Center не рендерит target identity из moderation history;
- PostgreSQL rehearsal проверяет две Persona одного Account и отсутствие утечки второй Persona через report projection;
- functional exact-head CI #770 green: backend, frontend, dependency-security и browser-smoke.

### Stage 6 checkpoint 20 — Upload / media security hardening ✅ `0.6.28-alpha.1`
- strict server MIME allowlist; unknown/SVG/HTML/legacy office/archive payloads rejected;
- decoded/streamed actual-byte caps replace trust in client-declared size;
- supported raster/audio/video/PDF/OOXML payloads require signature/magic validation;
- atomic UUID public writes, path confinement and partial-file cleanup;
- Messenger/Space share one validated upload pipeline with all-or-nothing per-message file/byte caps;
- Account-level media volume uses distributed Redis weighted limiting;
- raw Messenger `data:` metadata persistence removed; avatars restricted to raster images;
- upload responses add `nosniff`, sandbox CSP and same-origin resource policy; documents force attachment disposition;
- frontend accept list mirrors server policy;
- functional exact-head CI #758 green across backend, frontend, dependency-security and browser-smoke.

### Stage 6 checkpoint 19 — Realtime Redis pool profiling ✅ `0.6.27-alpha.1`
- privacy-safe pool snapshot показывает max/in-use/available/created/headroom/utilization без Redis URL/credentials/tickets/Account IDs;
- admin-only operations endpoint даёт текущий pool health;
- bounded profiler гоняет production RealtimeService primitives, а не synthetic raw-command microbenchmark;
- CI уменьшает pool до 12 connections и запускает 120 operations при concurrency 10;
- functional run #748: 0 errors, peak 11/12 in-use, 0 saturation samples; p95 19 ms рассматривается только как наблюдение конкретного runner, не SLO;
- machine gates контролируют error rate, broad p95 ceiling и saturation samples;
- полный functional exact-head CI #748 green.

### Stage 6 checkpoint 17 — Discovery query profiling / latency guard ✅ `0.6.25-alpha.1`
- privacy-safe profiler измеряет SQL statement/select count, DB time и wall time без params/IDs/payload;
- operational CLI поддерживает machine-readable JSON и max-statements/max-wall gates;
- PostgreSQL fixture содержит 260 Spaces плюс membership/shared/recent/upcoming candidate context;
- organic-v2 path ограничен 30 round-trips, explicit-filter path — 20;
- broad 5s wall ceiling ловит N+1/catastrophic regressions без flaky microbenchmark semantics;
- performance rehearsal входит в общий PostgreSQL CI gate.

### Stage 6 checkpoint 16 — Multi-source organic discovery candidates ✅ `0.6.24-alpha.1`
- default discovery pool больше не начинается только с newest catalog slice;
- bounded источники: membership/pending, recent distinct-author activity, upcoming Events/Activities, shared tags/purposes и freshness fallback;
- round-robin dedupe не позволяет одному источнику монополизировать общий cap;
- старые Spaces могут вернуться в candidate pool после новой активности;
- canonical eligibility остаётся до ranking, explicit filters сохраняют catalog semantics;
- `organic-v2` не использует paid/support/currency или legacy `Room.rating`;
- PostgreSQL + contract tests фиксируют source diversity, bounded work и privacy/ranking boundaries.

### Stage 6 checkpoint 15 — DST-correct recurring Activities ✅ `0.6.23-alpha.1`
- Activity хранит IANA timezone отдельно от canonical UTC instant;
- daily/weekly/monthly recurrence сохраняет локальное wall-clock время через DST;
- spring-forward gap и fall-back ambiguity имеют детерминированную политику;
- occurrence materialization/reminders используют тот же timezone-aware recurrence engine;
- SPA передаёт browser timezone, API валидирует IANA zone names;
- Amsterdam DST contract tests закрепляют spring/fall/weekly/monthly semantics.

### Stage 6 checkpoint 14.1 — Mobile room navigation / viewport hotfix ✅ `0.6.22-alpha.2`
- incoming route view монтируется сразу; outgoing frame fade-ится absolute и не может оставить пустой shell;
- room loading встроен в `space-main` skeleton вместо отдельного flex-loader;
- mobile room shell следует `100dvh` + shared topbar/bottom-nav/safe-area tokens без legacy minimum height;
- mobile navigation/composer/header density уменьшена;
- browser gate создаёт реальный Space, входит в комнату без reload и проверяет отсутствие document vertical overflow.

### Stage 6 checkpoint 1 — PostgreSQL migration baseline ✅ `0.6.0-alpha.1`
PostgreSQL 16 clean historical migration, schema-drift gate, synthetic legacy rehearsal и standalone ORM registry.

### Stage 6 checkpoint 2 — PostgreSQL recovery ✅ `0.6.1-alpha.1`
Portable dump/restore в отдельную DB с повторными Alembic/schema/data assertions.

### Stage 6 checkpoint 3 — Redis realtime ✅ `0.6.2-alpha.1`
Distributed tickets/TTL, presence, rate-limit, idempotency и cross-instance pub/sub при production semantics.

### Stage 6 checkpoint 4 — Redis restart recovery ✅ `0.6.3-alpha.1`
Real Redis outage/restart; production fail-closed; те же service objects восстанавливают commands/PubSub без process restart.

### Stage 6 checkpoint 5 — Multi-process WebSocket ✅ `0.6.4-alpha.1`
Два реальных Uvicorn process, shared Redis presence/pubsub, rolling worker restart и reconnect с новым one-time ticket.

### Stage 6 checkpoint 6 — Bounded backpressure ✅ `0.6.5-alpha.1`
Per-socket bounded outbound queue, ordering, non-blocking fan-out, queue/send-timeout slow-consumer isolation.

### Stage 6 stabilization patch ✅ `0.6.5-alpha.2`
Persistent systemd-owned listener, health-gated rolling deploy, staged SPA publish и messaging UX density pass.

### Stage 6 checkpoint 7 — Redis Sentinel failover/capacity ✅ `0.6.6-alpha.1`
Direct/Sentinel topology abstraction, real master+replica+3-Sentinel promotion rehearsal, same-service ticket/PubSub recovery и bounded concurrency до/после promotion.

### Stage 6 checkpoint 8 — Message notification policy / active context ✅ `0.6.7-alpha.1`
- account-level Messenger/Space in-app/sound preferences и opt-in flags external adapters;
- Redis connection-scoped Messenger active context с TTL/heartbeat; Space active context через distributed room presence;
- duplicate toast/sound suppression, когда получатель уже смотрит тот же context, без изменения authorization;
- offline external re-engagement только для Messenger по opt-in; offline Space chat никогда не создаёт background notification pressure;
- Space alert fan-out проходит active-membership и Account-block boundaries;
- единая SPA surface для Messenger/Space alerts с существующими private/chat sounds;
- Alembic migration + preference API + deterministic policy/active-context tests.

### Stage 6 checkpoint 9 — Durable unread-Messenger email delivery ✅ `0.6.8-alpha.1`
- durable privacy-minimal external delivery ledger без private message body и destination email;
- scheduled inactivity/cooldown/dedupe candidate worker только для opt-in Messenger re-engagement;
- current online presence, verified email, unread state и Account block/privacy повторно проверяются непосредственно перед delivery;
- новые DM не обходят Account-level email cooldown;
- SMTP provider поддерживает STARTTLS/implicit SSL, stable Message-ID и privacy-safe aggregate template;
- retryable/terminal provider failures разделены, retries используют bounded exponential backoff;
- delivery records claim-ятся через `FOR UPDATE SKIP LOCKED` + expiring lease; expired claim recoverable после crash;
- worker берёт по одному delivery claim непосредственно перед network send, чтобы batch не создавал преждевременный lease expiry;
- systemd oneshot/timer и installer выносят scheduler из FastAPI worker lifecycle;
- PostgreSQL integration test фиксирует concurrent disjoint claims + expired-lease recovery;
- legacy Messenger/Space User UID явно сопоставляется с Account через `legacy_user_uid`, Account block/privacy не смешивается с legacy identity.

### Stage 6 checkpoint 10 — Web Push / PWA Messenger delivery ✅ `0.6.9-alpha.1`
- Account-owned per-device PushSubscription model с endpoint fingerprinting и explicit register/status/remove lifecycle;
- VAPID provider: private key backend-only, SPA получает только public key/capability;
- browser notification permission запрашивается только после явного user gesture и никогда не появляется на bootstrap;
- offline Web Push queue создаётся только для Messenger; offline Space chat по-прежнему не создаёт external re-engagement pressure;
- privacy-minimal push payload не содержит private message body или sender identity и открывает только same-origin Messenger route;
- Redis presence, opt-in, unread state и Account block/privacy повторно проверяются перед provider send;
- общий `external_delivery_ledger` используется для Web Push с per-conversation cooldown/dedupe, `FOR UPDATE SKIP LOCKED`, expiring lease и bounded retry/backoff;
- terminal provider responses `404/410` удаляют протухшие subscriptions;
- отдельный systemd worker/timer выносит delivery из Uvicorn lifecycle;
- service worker получил push/click flow без расширения static-only cache boundary;
- logout/session teardown отвязывает local push subscription best-effort для shared-browser safety;
- Notifications UI получил email/Web Push controls; deterministic provider/privacy/PWA guards закреплены в CI.

### Stage 6 checkpoint 11 — External delivery observability ✅ `0.6.19-alpha.1`
- aggregate email/Web Push metrics показывают pending/due backlog, processing, expired claims, retry pressure, delivered/failed и failure-class counts без Account IDs или message content;
- stale backlog alert thresholds отделены от delivery policy и не меняют suppress/retry behavior;
- admin-only operations endpoint и standalone CLI дают machine-readable health;
- `--require-healthy` fail-ит на stale due backlog или expired processing claims;
- email/Web Push workers пишут structured completion events с aggregate counters;
- structured-log helper fail-closed отклоняет token/secret/password/email destination/push endpoint/key material/message-content field names;
- PostgreSQL integration проверяет operational detection и отсутствие seeded private identifiers в metrics output;
- CI запускает observability CLI как отдельный machine gate.

### Stage 6 checkpoint 12 — Browser / security launch gate ✅ `0.6.20-alpha.1`
- SPA browser default переведён на same-origin `/api`; dev/preview proxy обслуживает HTTP + WebSocket без legacy localhost cross-origin fallback;
- CSRF требует signed HttpOnly cookie и matching in-memory `X-CSRF-Token` header proof;
- unsafe requests сами bootstrap-ят CSRF, поэтому registration/login/refresh не зависят от mount-time race;
- Playwright gate выполняет registration, reload/refresh rotation, Messenger route, logout/revocation и login;
- matrix: Chromium, Firefox, WebKit/Safari-compatible engine и narrow mobile Chromium;
- access bearer не сохраняется в local/session storage, notification permission не запрашивается на bootstrap;
- CI блокирует возврат `http://localhost:9000` browser fallback;
- production dependencies проходят обязательные npm/pip vulnerability audits без allow-list исключений;
- functional exact-head CI #637 green: dependency-security + frontend + full backend + all browser projects.

### Stage 6 checkpoint 14 — Space member-capacity concurrency ✅ `0.6.22-alpha.1`
- direct join, invitation accept и pending-member approval используют общий PostgreSQL admission lock;
- active membership COUNT выполняется после lock, поэтому `member_limit` не переполняется конкурентными запросами;
- duplicate same-Account join остаётся идемпотентным;
- deterministic PostgreSQL rehearsal конкурирует за последнее место между разными activation paths;
- Space service UUID lookup исправлен: public UUID больше не передаётся как integer primary key.

### Stage 6 checkpoint 13.1 — Mobile routed-content hotfix ✅ `0.6.21-alpha.2`
- route transition теперь анимирует стабильный DOM wrapper и не зависит от fragment-root конкретного view;
- browser gate проверяет реальную видимость Space Discovery content после registration/reload/login;
- JWT issuance получил unique `jti`, исключающий same-second refresh-token collisions.

### Stage 6 checkpoint 13 — UI motion / loading polish ✅ `0.6.21-alpha.1`
- route transitions используют короткий out-in motion и delayed/min-visible progress, без искусственного ожидания быстрых переходов;
- shared state/popover/skeleton/spinner primitives поддерживают `prefers-reduced-motion`;
- Create Space modal, Persona dropdown, registration steps и profile settings больше не появляются/исчезают мгновенно;
- Messenger получил честные loading skeletons, error/retry и перестал показывать ложное empty-state до ответа API;
- ключевые login/register/profile/join/create actions показывают pending feedback;
- root `update.sh` восстановлен как совместимый entrypoint к `ops/deploy.sh`;
- functional exact-head CI #645 green: frontend, dependency-security, full backend и Chromium/Firefox/WebKit/mobile browser-smoke.

### Stage 6.8 checkpoint 1 — Trust & Safety foundation ✅ `0.6.10-alpha.1`
- platform report intake отделён от Space-local moderation и поддерживает Persona, Messenger message и Space message reports;
- server-owned priority, duplicate/rate guard, moderator queue claim/release и privacy-bounded evidence access;
- append-only audit trail и target-visible public explanation;
- platform role authority hierarchy (`user=0`, `moderator=50`, `admin=100`) + explicit moderation permissions;
- durable Account-level capability restrictions со scope, temporary/permanent duration, revoke history и authority snapshots;
- server-side enforcement для Messenger/Space chat, media upload, Space create/join/invite, Persona edit и organic discovery publication;
- independent platform restriction appeal queue с overturn/revoke semantics;
- moderator UX для triage/evidence/restrictions/appeals;
- AI-copilot boundary закреплён: AI помогает, но не является punitive authority.

### Stage 6.8 checkpoint 2 — Full Account suspension ✅ `0.6.11-alpha.1`
- `account.access` доступен только platform-wide и требует elevated permission + strict authority hierarchy;
- выдача suspension отзывает существующие Identity v2 sessions и legacy device sessions;
- stateless access JWT не обходит санкцию: authenticated HTTP requests перепроверяют durable PostgreSQL restriction;
- login/refresh поддерживают deliberately restricted session, чтобы пользователь видел причину и мог подать appeal;
- минимальный разрешённый контур под suspension: identity bootstrap, собственное restriction state, appeal creation/history и logout;
- realtime ticket re-check после consume закрывает гонку «ticket получен перед suspension»;
- distributed account-control disconnect закрывает уже открытые Messenger/Space WebSocket connections во всех workers;
- SPA переводит suspended Account в restricted Safety Center с причиной, сроком, appeal state и logout;
- revoke/expiry не оживляет ранее отозванную session: требуется нормальная повторная аутентификация;
- PostgreSQL integration и contract tests фиксируют session/HTTP/realtime/scope semantics.

### Stage 6.8 checkpoint 3 — Moderation permission hierarchy ✅ `0.6.12-alpha.1`
- platform queue access отделён от authority выдавать санкции: добавлены `moderation.platform.restrict`, `moderation.platform.revoke` и `moderation.platform.appeal.review`;
- обычный moderator может выдавать и снимать только те restrictions, для которых у него есть соответствующий action permission и достаточный authority;
- permanent restriction и `account.access` сохраняют отдельные elevated permissions и не становятся доступны только из-за высокого role level;
- direct revoke требует revoke permission, authority выше target и authority не ниже snapshot исходного actor, поэтому peer moderator не может отменить решение более сильного admin;
- appeal reviewer требует отдельного review permission плюс authority/sensitivity checks; independent-review discovery учитывает только реально eligible reviewers;
- action endpoints используют specific dependencies вместо общего `moderation.platform.manage`, а capability discovery возвращает только реально доступные текущему actor действия;
- Alembic migration синхронизирует permission sequence после исторического explicit-ID seed и раздаёт новые permissions базовым moderator/admin roles;
- PostgreSQL integration фиксирует manage-only custom role denial, peer revoke, запрет override admin sanction, elevated permanent/account-access path и отдельный appeal-review permission.

### Stage 6.8 checkpoint 4 — Moderation AI copilot ✅ `0.6.13-alpha.1`
- provider-neutral advisory AI layer отделён от punitive moderation authority;
- отдельный `moderation.platform.ai.assess` permission ограничивает доступ к provider-backed assessment;
- AI работает только по claimed report и получает privacy-minimal evidence envelope без Account identifiers, unrelated dialog history и attachment URLs;
- свободный reporter description не отправляется внешнему provider, чтобы не расширять PII surface сверх пожалованного объекта;
- AI может рекомендовать только `none` или bounded temporary restriction; `account.access`, permanent sanction, revoke и appeal decision запрещены контрактом;
- durable recommendation хранит structured summary/severity/confidence/rationale и human outcome, но не raw prompts/responses/chain-of-thought;
- assessment budget на report ограничивает provider-cost amplification;
- moderator UI позволяет принять suggestion как черновик, взять за основу с изменением или отклонить; реальная санкция проходит обычный hierarchy/permission enforcement;
- provider/schema/privacy/persistence/audit boundaries покрыты deterministic и PostgreSQL integration tests.

### Stage 6.8 checkpoint 5 — Anti-spam / raid abuse signals ✅ `0.6.14-alpha.1`
- durable privacy-minimal behavioral signal ledger хранит counters/window/threshold evidence без message body, private transcript и attachment URLs;
- Messenger и Space realtime rate-limit pressure создают deduped advisory signals;
- Messenger distinct-recipient burst выявляет массовые DM-контакты в bounded window;
- Space invitation distinct-recipient burst выявляет invite-spam pressure;
- все thresholds и windows конфигурируемые и имеют безопасные нижние/верхние границы;
- moderator UI получил отдельную очередь signal evidence со статусами open/reviewed/dismissed;
- сигнал сам по себе не создаёт restriction, не меняет authority и не является автоматическим verdict;
- PostgreSQL integration закрепляет durable dedupe/upsert и отсутствие punitive side effects.

## Stage 6 — Pre-beta hardening 🚧 `0.6.x-alpha`

### 6.1 Data / migrations 🚧
- ✅ PostgreSQL 16 integration, historical clean migration, zero drift;
- ✅ synthetic legacy rehearsal и backup/restore drill;
- ⏳ anonymized production-like snapshot rehearsal;
- ✅ member-capacity concurrency hardening;
- ✅ IANA timezone storage и DST-correct recurring wall-clock semantics.

### 6.2 Redis / realtime reliability ✅ baseline complete
- ✅ distributed Redis semantics и production fail-closed;
- ✅ restart recovery без process restart;
- ✅ multi-process WebSocket / rolling reconnect;
- ✅ bounded slow-client isolation;
- ✅ direct/Sentinel topology, real promotion, PubSub/ticket recovery;
- ✅ bounded concurrency до/после failover.

Large-scale throughput/pool saturation остаётся в performance/observability workstream.

### 6.3 Notification worker / message delivery 🚧
- ✅ product matrix: offline external delivery только Messenger; Space alerts online-only;
- ✅ `private_notification.mp3` / `chat_notification.mp3` mapping;
- ✅ durable message preferences и deterministic policy tests;
- ✅ Redis Messenger active-context TTL + Space context через distributed presence;
- ✅ scheduled unread-Messenger email nudge: inactivity threshold + Account cooldown + dedupe + opt-out;
- ✅ durable external email ledger + SMTP provider + retry/backoff + expiring claim lease;
- ✅ concurrent worker / `SKIP LOCKED` claim validation и expired-lease recovery;
- ✅ external email scheduler/service unit вне web-worker lifecycle;
- ✅ Web Push adapter: Service Worker/Push API/Notifications API + VAPID + per-device subscription lifecycle;
- ✅ terminal push subscription cleanup + retry/backoff integration;
- ✅ notification preferences UI для email/Web Push;
- ✅ external delivery metrics/health + structured worker completion logs;
- ⏳ provider-side telemetry, load/idempotency profiling.

### 6.4 Discovery / performance 🚧
- ✅ multi-source bounded candidate generation вместо newest-catalog bias;
- ✅ query/DB profiling и bounded ranking latency/load guard;
- ✅ privacy/block regression на большом candidate set;
- ✅ bounded realtime/Redis pool utilization + near-limit profiling;
- ⏳ sustained production-like soak / mass reconnect / provider-specific capacity profiling.

### 6.5 Security/privacy 🚧
- ✅ session/cookie/CSRF browser contract: explicit signed cookie + matching header proof;
- ✅ registration/login/refresh automated Chromium/Firefox/WebKit/mobile compatibility gate;
- ✅ upload/media baseline review for current allowlist;
- ⏳ malware scanning/CDR + shared/object storage/public URL policy for broader file support;
- ✅ moderation/report/appeal privacy projection audit;
- Account block coverage + privacy side-channel + secret/logging review;
- financial threat model до real payments.

### 6.6 Operations / observability 🚧
- ✅ multi-worker Uvicorn supervisor + persistent systemd socket;
- ✅ `/health/live` и dependency-aware `/health/ready`;
- ✅ health-gated rolling deploy + staged asset-first SPA publish;
- ✅ external Messenger email systemd scheduler/service + fail-fast provider config installer;
- ✅ external Messenger Web Push systemd scheduler/service + VAPID preflight installer;
- ✅ Redis pool utilization/headroom metrics + bounded profile gate;
- ⏳ Sentinel topology/promotion/replication-lag metrics и alerting;
- ✅ email/push durable-ledger delivery metrics/health;
- ⏳ SMTP/Web Push provider-side health/latency telemetry;
- ⏳ structured logs/error tracking, incident procedure;
- 🚧 deployment/recovery runbook;
- ⏳ backup retention/encryption/off-site storage + RPO/RTO;
- ⏳ shared/object storage и expanded compatibility matrix.

### 6.7 UX/accessibility / browser compatibility 🚧
- 🚧 compact messaging composer/density and information-panel polish;
- ✅ transient authenticated bootstrap retry;
- ✅ historical Safari registration defect audit;
- ✅ Playwright WebKit registration/login/refresh through production-like same-origin proxy;
- ✅ Chromium + Firefox + WebKit + narrow mobile auth/session critical journey;
- ✅ notification preferences UI и baseline PWA Web Push permission/subscription UX;
- ⏳ iOS/iPadOS installed Home Screen push flow в device/browser matrix;
- ⏳ keyboard/focus, contrast/mobile/narrow viewport, onboarding and terminology audit;
- 🚧 error/empty/offline consistency.

### 6.8 Trust & Safety / moderation launch readiness 🚧

Базовый platform moderation контур, full `account.access`, fine-grained human permission hierarchy и provider-neutral AI-copilot уже реализованы; до публичной beta остаются abuse-automation и операционные слои.

- ✅ единый platform report flow для Persona, Messenger message и Space message; media-attachment specialization ещё впереди;
- ✅ report taxonomy/priority baseline, duplicate collapse и rate guard;
- ✅ moderator queue с ownership/claim и triage/in-review/resolved/escalated states;
- ✅ privacy-bounded evidence snapshot/reference и audit просмотра evidence;
- ✅ platform capability restrictions по Account с scope, сроком, reason code, public explanation и permanent/elevated permissions;
- ✅ Space-local moderation отделена от platform Trust & Safety;
- ✅ Account-level hierarchy + capability enforcement, включая full `account.access` session/HTTP/realtime suspension;
- ✅ immutable/auditable restriction history и отдельный revoke event;
- ✅ platform restriction appeal queue с claim/review и independent-review preference;
- ✅ internal moderator UX для report review, evidence, issue/revoke restrictions и appeals;
- ✅ hierarchy/permission hardening: отдельные issue/revoke/appeal-review permissions, elevated permanent/account-access powers и issuer-authority floor для revoke;
- ✅ AI assessment model + provider-neutral adapter + recommendation UI (`accepted / modified / rejected / not_used`) с privacy-minimal evidence и bounded assessment budget;
- 🚧 anti-spam/raid baseline: ✅ realtime rate-limit pressure, ✅ DM distinct-recipient burst, ✅ invite-recipient burst; ⏳ repeated unsolicited-contact correlation, mass-join/leave и broader automation pressure;
- ⏳ media/upload abuse workflow: quarantine/remove/review hooks без автоматической выдачи модератору лишних приватных данных;
- ⏳ moderation metrics: queue age, response time, action/appeal counts, overturned decisions, AI recommendation outcomes; без KPI, стимулирующих больше санкций;
- ⏳ privacy/retention policy для reports/evidence/AI envelopes и redaction/export procedures;
- ⏳ load/incident rehearsal: spam-wave/raid, moderator backlog, AI/provider outage, Redis/backend outage во время incident response.

**Beta gate:** `report → triage/AI assist → human claim/review → hierarchy/permission check → restriction → runtime enforcement → audit → target notification → appeal → independent review/revoke/uphold` должен работать end-to-end для основных типов abuse.

### 6.9 Sustainable monetization / business viability 🚧

Цель — финансировать инфраструктуру, storage/traffic, email/push, поддержку и Trust & Safety без продажи trust, moderation authority или organic ranking.

- ⏳ построить cost model: PostgreSQL/Redis/compute, storage, egress/CDN, uploads/media, email, push, backups, observability, support/moderation; считать cost per active Account / message / stored GB там, где метрика полезна;
- ⏳ определить минимальный monthly revenue target: infrastructure + moderation/support + payment/provider fees + safety reserve, а не только «сервер пока оплачивается»;
- ⏳ выбрать 1–2 monetization hypotheses для beta и не распыляться на полноценную игровую экономику;
- ⏳ основной кандидат — PubChat Plus: косметика/темы, расширенное оформление Persona/Space, дополнительные convenience-функции и разумные resource limits без деградации базового общения;
- ⏳ отдельный cosmetic catalog / gifts / Space appearance entitlements, не влияющие на trust, permissions, moderation или discovery ranking;
- ⏳ проверить модель дополнительных storage/media limits для платных Account/Space, сохраняя бесплатный базовый messaging path;
- ⏳ позже проверить real creator/Space support с прозрачной комиссией платформы; это отдельный financial/security/legal checkpoint, не продолжение текущих бесплатных cosmetic gestures;
- ⏳ исследовать professional/community plan для управляемых Spaces: дополнительные admin/analytics/storage инструменты, но без покупки места в organic discovery;
- ⏳ entitlement model server-side: subscription/cosmetic/resource entitlement отдельно от Account trust, role и permissions;
- ⏳ pricing/retention experiments: conversion, churn, ARPPU/ARPU и willingness-to-pay без dark patterns, искусственных streak losses и давления через личные сообщения;
- ⏳ payment provider, receipts/refunds/chargebacks, tax/legal/privacy requirements и fraud controls до первого real-money transaction;
- ⏳ observability для revenue pipeline без хранения лишних платёжных данных в PubChat;
- ⏳ зафиксировать бесплатное ядро продукта и платные границы до beta, чтобы monetization не переделывала архитектуру после роста.

**Жёсткие ограничения монетизации:** деньги не покупают trust, verification-as-authority, moderation immunity, Space/platform moderator role, обход block/privacy/rate-limit, преимущество в organic discovery или право сильнее воздействовать на других пользователей. Appeals/reporting/security recovery также не становятся платными функциями.

## Beta

Beta назначается только когда launch-critical journeys работают end-to-end, production-like gates пройдены, observability доступна и нет известных P0/P1 blockers. Помимо technical reliability, до публичной beta должен существовать рабочий moderation/Trust & Safety контур и понятная операционная модель его поддержки. Monetization может не быть полностью включена в первой beta, но до расширения аудитории должны быть выбраны monetization hypothesis, cost model и бесплатные/платные границы продукта, чтобы инфраструктура и moderation не зависели от бессрочного ручного финансирования.

Ориентир `0.9.0-beta.1` не является календарным обещанием.

## Stable 1.0

`1.0.0` — первый public stable release с explicit API/data compatibility commitment, рабочей moderation operations model и устойчивым планом финансирования инфраструктуры/поддержки.

## Постоянные инварианты

- Account != Persona.
- Reputation/achievement != Permission.
- Space moderator != Platform moderator.
- Деньги не покупают trust/moderation authority.
- Платный entitlement не расширяет privacy/access/abuse permissions.
- Account block нельзя обойти другой Persona.
- Discovery ranking не расширяет eligibility/privacy и не покупается gift/support.
- PostgreSQL — durable source of truth; Redis — ephemeral realtime/presence/context layer.
- Production realtime не использует silent process-local fallback.
- Redis recovery/failover не требует process restart и не превращает async-replicated ephemeral state в durable guarantee.
- Slow realtime consumer не блокирует fan-out другим соединениям.
- Offline external message re-engagement относится только к Messenger и требует opt-in; Space chat не создаёт background spam отсутствующему Account.
- Active context подавляет duplicate UX, но не является authorization state.
- Notification routing не расширяет block/privacy/visibility.
- External delivery ledger не хранит private message text или destination email.
- Web Push payload не хранит/не раскрывает private message body или sender identity; VAPID private key остаётся server-only.
- Background scheduler не запускается внутри каждого web worker.
- Service worker не является storage для auth/private API data.
- Production listener принадлежит process manager/systemd; routine deploy rolling, frontend publish staged.
- Rolling deploy требует expand/contract-compatible schema changes.
- Moderation decision имеет scope/reason/audit trail и не покупается за деньги.
- Platform queue access не означает право на sanction actions: issue/revoke/appeal review разделены explicit permissions и authority checks.
- `account.access` является elevated platform-only capability; он не отменяет право пользователя увидеть причину и подать appeal.
- AI moderation не является источником punitive authority в beta baseline.
- Communication quality first; никакой тюремной терминологии.
- SPA — первый клиент, contracts reusable для Android/iOS.

### Stage 6.8 checkpoint 6 — Reported media moderation ✅ `0.6.15-alpha.1`
- отдельный `moderation.platform.media.manage` permission и hierarchy checks;
- durable reversible quarantine/restore/remove state для пожалованных локальных attachments;
- private evidence storage вне публичного `/uploads` tree и path-confinement;
- cross-filesystem move/rollback semantics;
- moderator UI controls и PostgreSQL/filesystem integration coverage;
- AI/automation не получают punitive media authority;
- автоматическое deletion evidence отложено до формализованной retention policy.



### Stage 6.8 checkpoint 7 — Trust & Safety operations ✅ `0.6.16-alpha.1`
- aggregate queue/decision/appeal/AI/signal/restriction metrics без пользовательского содержимого и identifiers;
- moderator operations dashboard и policy status;
- incident rehearsal matrix, включая concurrent claim, AI outage, appeal overturn, account.access и media workflow;
- default-off protective holds: ≥2 high/critical signal buckets, 5–15 минут, только Messenger send / invitations;
- privileged Accounts и sensitive capabilities исключены;
- per-Account serialization исключает duplicate auto-holds при concurrent detectors;
- functional exact-head CI #579 green до release sync.
- осталось отдельно: private moderation evidence retention/secure expiry и production calibration до enablement automation.



### Stage 6.8 checkpoint 8 — Private moderation evidence retention ✅ `0.6.17-alpha.1`
- durable `retention_due_at` / `purged_at` lifecycle для removed reported-media evidence;
- configurable 90-day baseline (bounded 7–365 days) и полный window после latest removal/report/appeal finality;
- active report и pending linked appeal блокируют expiry;
- eligible rows выбираются bounded batch через `FOR UPDATE SKIP LOCKED` без starvation deferred cases;
- private storage disjoint from `/uploads`, 0700/0600 + systemd `UMask=0077`;
- record-directory confinement запрещает cross-record/path traversal deletion;
- expiry удаляет private bytes и file-locating metadata, сохраняя decision/audit linkage;
- отдельный daily systemd worker + aggregate due/purged metrics;
- application-level expiry не заявляется как forensic wipe для snapshots/backups;
- functional exact-head CI #595 green до release sync.
- осталось отдельно: production calibration protective holds и backup/snapshot lifecycle alignment.



### Stage 6.8 checkpoint 9 — Protective-hold calibration / storage lifecycle ✅ `0.6.18-alpha.1`
- canonical `off | shadow | enforce` modes;
- shadow пишет would-hold evaluations, но не создаёт restrictions;
- explicit human labels `true_positive / false_positive / unclear`;
- per-signal-family false-positive gate и conservative candidate-capture proxy;
- enforce требует одновременно data-ready calibration и explicit operational approval;
- legacy ENABLED flag не обходит новый gate;
- calibration CLI и moderator dashboard;
- declared backup/snapshot retention preflight для private moderation evidence;
- retention-worker installer fail-closed без storage lifecycle declarations;
- CI rehearsal проверяет shadow/no-sanction, bad-FP blocking, no-approval blocking и allow-listed enforce path;
- synthetic CI labels не считаются production calibration data.

Открыто после checkpoint: накопление реальной human-reviewed shadow выборки, operational approval decision и проверка, что заявленные backup/snapshot сроки реально настроены у storage provider.

