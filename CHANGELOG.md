# PubChat — история версий

Формат до стабильного релиза: `MAJOR.MINOR.PATCH-channel.N`.

## Unreleased — исправления подготовки Web/PWA, 2026-10-26

- Установлены тайм-ауты HTTP/CSRF/refresh, временная ошибка сети больше не уничтожает сессию (проверенный 401 — исключение).
- Messenger и Space защищены от дублирующих/зависших one-time-ticket WebSocket-подключений и восстанавливаются после неожиданного закрытия, включая код 1000.
- При возвращении из фонового режима Safari или BFCache после длительного простоя выдаются новые realtime tickets.
- Глобальный bootstrap больше не повторяет уже подтверждённый identity-запрос; подготовка Space не ожидает завершения Messenger handshake.
- Внешний CSS иконок переведён на неблокирующую загрузку, чтобы проблемы стороннего CDN не останавливали первый показ SPA.
- В CI добавлены проверки обоих realtime-клиентов, восстановления сессии, Safari lifecycle и первого отображения.

Это кодовые исправления, **не опубликованный релиз**. Точные причины задержки production API/DB/TLS, доставка через iPhone Safari и производительность под реальной нагрузкой требуют проверки сервера и физического устройства. VERSION пока не изменён.

## [0.6.30-alpha.1] — 2026-10-03

Stage 6 checkpoint 22 — PostgreSQL pool observability baseline.

- SQLAlchemy pool size, max overflow и checkout timeout вынесены в bounded environment settings вместо hardcoded значений;
- admin-only `GET /admin/operations/postgres-pool` показывает aggregate checked-out/checked-in/overflow/headroom/utilization и near-capacity health;
- utilization/headroom thresholds являются только observability policy и не меняют pool size или traffic behavior;
- response privacy contract не содержит DB URL/credentials, SQL text/parameters, Account IDs или connection identities;
- multi-worker semantics зафиксированы явно: `scope=current_process`, потому что каждый application process владеет независимым SQLAlchemy pool;
- standalone pool-health CLI намеренно не добавлен: отдельный процесс наблюдал бы собственный новый pool и создавал ложную картину live workers;
- operations docs фиксируют capacity planning как per-process pool × backend worker count плюс отдельные PostgreSQL clients;
- PyJWT обновлён до 2.15.0; production dependency audit остаётся обязательным CI gate;
- functional exact-head CI #787 полностью зелёный: backend, frontend, dependency-security и browser-smoke.

Checkpoint закрывает первый PostgreSQL capacity-observability slice, но не cross-process/server-wide telemetry и не production-like sustained SQL workload profiling.

## [0.6.29-alpha.1] — 2026-09-29

Stage 6 checkpoint 21 — moderation/report/appeal privacy projection hardening.

- reporter-facing Trust & Safety API больше не использует moderator projection и не раскрывает target Account UID, target primary Persona, queue priority, moderator assignment или internal resolution code;
- жалоба сохраняет только идентификатор реально пожалованного source object; другая Persona того же Account не выводится и не коррелируется;
- legacy Space report history также перестал выводить target Account→primary Persona projection;
- target-facing `/trust-safety/v1/me/restrictions` теперь скрывает moderator actor UID, target Account UID, report linkage, internal reason taxonomy и restriction origin;
- moderator-only restriction lookup явно использует internal projection и сохраняет operational данные для работы очереди;
- Safety Center больше не ожидает и не показывает target identity в истории собственных жалоб;
- contract + PostgreSQL integration tests фиксируют разделение reporter/target и moderator projections, включая сценарий двух Persona одного Account;
- functional exact-head CI #770 полностью зелёный: backend, frontend, dependency-security и browser-smoke.

Цель checkpoint — не скрыть объект, на который пользователь сам пожаловался, а не допустить, чтобы moderation API раскрывал дополнительные Account/Persona связи и внутреннюю операционную метаинформацию.

## [0.6.28-alpha.1] — 2026-09-29

Stage 6 checkpoint 20 — upload/media security hardening.

- upload pipeline теперь принимает только явный server MIME allowlist; unknown/SVG/HTML/legacy office/archive types отклоняются до сохранения;
- base64/data-URL parsing стал строгим, а size limits применяются к реально decoded/streamed bytes, а не к client-declared size;
- supported raster/audio/video/PDF/OOXML uploads проходят signature/magic verification; DOCX/XLSX дополнительно проверяются как ожидаемый Office ZIP shape;
- публичные файлы сохраняются atomic write + UUID filename с path confinement и cleanup partial files;
- Messenger/Space attachments используют единый validated pipeline; per-message file-count/byte cap работает all-or-nothing;
- Account-level media byte-rate budget применяется через distributed Redis weighted limiter;
- Messenger больше не сохраняет raw `data:` URI в PostgreSQL media metadata;
- avatar upload ограничен raster image types, а legacy profile debug `print()` с потенциальным base64 payload удалён;
- `/uploads` получает `X-Content-Type-Options: nosniff`, sandbox CSP и same-origin resource policy; documents принудительно отдаются как attachment;
- frontend picker синхронизирован с server allowlist;
- tests покрывают MIME spoofing, invalid base64, lied size, multipart byte caps, cleanup, Office ZIP shape, response headers, metadata normalization и weighted byte limiter;
- functional exact-head CI #758 полностью зелёный: backend, frontend, dependency-security и browser-smoke.

Этот checkpoint уменьшает upload attack surface, но не заменяет полноценный malware scanning/CDR pipeline для произвольных документов и архивов; такие форматы остаются запрещёнными до отдельной политики.

## [0.6.27-alpha.1] — 2026-09-29

Stage 6 checkpoint 19 — realtime Redis pool profiling baseline.

- добавлен privacy-safe snapshot Redis connection pool: max/in-use/available/created/headroom/utilization без Redis URL, credentials, ticket values или Account identifiers;
- admin-only `GET /admin/operations/realtime-redis` показывает текущий pool health и configured alert thresholds;
- `REDIS_POOL_ALERT_UTILIZATION_PERCENT` и `REDIS_POOL_MIN_HEADROOM_CONNECTIONS` влияют только на observability, не меняя pool size/retry/traffic policy;
- standalone `python -m workers.realtime_pool_profile` выполняет bounded profile через реальные RealtimeService primitives: ticket round-trip, presence register/touch/unregister и idempotency claim/release;
- CLI имеет machine gates по error rate, p95 latency и saturation samples;
- CI специально уменьшает pool до 12 connections и запускает 120 operations при concurrency 10;
- functional CI #748: 120/120 completed, 0 errors, peak 11/12 in-use, 91.67% observed utilization, 0 saturation samples, p95 19 ms на конкретном GitHub runner;
- эти latency/throughput цифры не являются production SLO; checkpoint фиксирует bounded regression/capacity signal, а не универсальный benchmark;
- полный functional exact-head CI #748 зелёный: backend, frontend, dependency-security и Chromium/Firefox/WebKit/mobile browser-smoke.

## [0.6.26-alpha.1] — 2026-09-28

Stage 6 checkpoint 18 — large-pool discovery privacy/block regression.

- PostgreSQL rehearsal насыщает discovery 260 public Spaces и отдельными privacy/block sentinel Spaces, то есть превышает общий candidate-pool cap;
- public Space владельца, заблокированного viewer Account, не появляется как новая рекомендация без существующей membership relation;
- existing active membership в Space blocked owner сохраняется как отдельная community relation и не удаляется discovery-фильтром;
- private Space без membership не попадает в projection даже если recent activity/upcoming Event сделали его внутренним candidate;
- private Space с pending membership может быть показан как известная заявка, но не раскрывает recent-conversation/upcoming-event live context;
- response дополнительно проверяется на отсутствие sentinel name/UID закрытого Space;
- privacy/block path остаётся внутри существующего discovery performance budget: ≤30 SQL statements и broad <5s wall ceiling;
- functional exact-head CI #740 полностью зелёный: backend/PostgreSQL privacy rehearsal, frontend, dependency-security и Chromium/Firefox/WebKit/mobile browser-smoke.

## [0.6.25-alpha.1] — 2026-09-28

Stage 6 checkpoint 17 — discovery query profiling / latency guard.

- добавлен privacy-safe discovery profiler: считает aggregate SQL statement/select count, суммарное DB cursor time и wall time без SQL params, Account/Space IDs или result payload;
- standalone CLI `python -m workers.discovery_profile --viewer-uid ...` умеет печатать JSON profile и fail-ить по `--max-statements` / `--max-wall-ms`;
- PostgreSQL rehearsal создаёт 260 Spaces с memberships, tags, recent activity и upcoming Events, то есть candidate set превышает общий discovery pool cap;
- default `organic-v2` path обязан укладываться максимум в 30 SQL statements независимо от количества кандидатов;
- explicit purpose-filter path обязан укладываться максимум в 20 SQL statements и быть дешевле organic path по round-trips;
- оба пути имеют широкий 5s wall ceiling: это guard от N+1/catastrophic scan, а не нестабильный microbenchmark;
- profiler schema намеренно содержит только aggregate operational metrics;
- functional exact-head CI #731 полностью зелёный: backend/PostgreSQL performance rehearsal, frontend, dependency-security и Chromium/Firefox/WebKit/mobile browser-smoke.

## [0.6.24-alpha.1] — 2026-09-28

Stage 6 checkpoint 16 — multi-source organic discovery candidates.

- default organic discovery больше не ограничен только newest catalog slice: candidate pool собирается из нескольких независимых bounded источников;
- источники включают current/pending membership, recent distinct-author activity, upcoming Events/materialized Activities, shared tags/purposes и freshness fallback;
- источники interleave-ятся round-robin с dedupe, поэтому один источник не может полностью вытеснить остальные до общего cap 200;
- старый Space может снова попасть в discovery после новой социальной активности, даже если давно вышел за пределы newest slice;
- explicit q/purpose/tag filter mode сохраняет canonical bounded catalog semantics;
- canonical Space eligibility/visibility/membership policy по-прежнему применяется до ranking и projection;
- алгоритм повышен до `organic-v2`;
- paid/support/currency signals и legacy `Room.rating` по-прежнему не участвуют ни в candidate generation, ни в scoring;
- добавлены индексы для recent activity, active-room freshness, purpose и upcoming event candidate sources;
- PostgreSQL rehearsal доказывает, что старый активный Space возвращается в bounded candidate pool;
- functional exact-head CI #722 полностью зелёный: backend, frontend, dependency-security и Chromium/Firefox/WebKit/mobile browser-smoke.

## [0.6.23-alpha.1] — 2026-09-23

Stage 6 checkpoint 15 — DST-correct recurring Activities.

- `space_activities` получил durable IANA `timezone_name`; существующие записи мигрируют с `UTC`, сохраняя прежнее расписание;
- recurring daily/weekly/monthly arithmetic выполняется в локальном календаре выбранной timezone, а durable `starts_at`/occurrence instants остаются UTC;
- weekly/monthly серии сохраняют локальное wall-clock время при переходе CET/CEST и других DST boundary;
- nonexistent spring-forward wall time сдвигается вперёд на DST gap только для конкретного occurrence, следующий occurrence возвращается к исходному wall-clock времени;
- ambiguous fall-back wall time использует первый occurrence (`fold=0`) как детерминированную политику;
- materialized Activity occurrences используют тот же timezone-aware recurrence engine, поэтому reminders и UI не расходятся с `next_starts_at`;
- Activity API валидирует реальные IANA timezone names;
- SPA передаёт browser IANA timezone при создании Activity и показывает выбранную timezone рядом с datetime-local input;
- contract tests детерминированно проверяют Amsterdam spring-forward, fall-back, weekly и monthly semantics;
- functional exact-head CI #702 полностью зелёный: backend/PostgreSQL, frontend, dependency-security и Chromium/Firefox/WebKit/mobile browser-smoke.

## [0.6.22-alpha.2] — 2026-09-23

Hotfix — mobile room navigation / viewport fit.

- SPA route transition больше не использует `mode="out-in"`: новая route view монтируется сразу, а старая кратко fade-ится поверх неё с `pointer-events: none`, поэтому переход в комнату не может оставить shell без content до reload;
- outgoing route frame во время leave становится absolute и не раздувает document flow;
- room loading перенесён внутрь `space-main` как skeleton; старый standalone Loader больше не участвует отдельным flex-соседом;
- mobile room height вычисляется из реального `100dvh`, topbar, bottom-nav и safe-area; legacy `min-height: 32rem` на mobile сброшен;
- mobile topbar/bottom-nav и composer/header уплотнены, bottom-nav reserve синхронизирован с его реальной высотой;
- browser-smoke создаёт настоящий Space через UI и переходит в `/spaces/:uid` без reload, проверяя видимый room heading;
- mobile Chromium дополнительно проверяет отсутствие document-level vertical overflow и что room заканчивается перед fixed bottom-nav;
- functional exact-head CI #693 полностью зелёный: backend, frontend, dependency-security и browser-smoke.

## [0.6.22-alpha.1] — 2026-09-22

Stage 6 checkpoint 14 — Space member-capacity concurrency hardening.

- `member_limit` теперь защищён единым PostgreSQL admission lock на `space_settings` для direct join, invitation accept и manager approval;
- legacy/partial Space без settings использует Room-row fallback lock вместо возврата к racy COUNT;
- после lock выполняется повторный active-membership COUNT, поэтому два параллельных запроса не могут занять одно последнее место;
- concurrent join одного Account идемпотентен: membership повторно читается после lock и не гоняется в `uq_space_membership`;
- manager approval после lock повторно блокирует/re-validates target membership и role/status boundaries;
- PostgreSQL rehearsal намеренно удерживает admission lock и проверяет join-vs-invite, join-vs-approval и duplicate same-Account join;
- concurrency test fail-fast: bounded wait/timeout и гарантированное освобождение gate transaction;
- rehearsal обнаружил и исправил отдельный UUID bug: Space service больше не вызывает `db.get(Room, space_uid)` при integer PK `Room.id`; update/archive/join/leave/member-role загружают Space по публичному `Room.uid`;
- functional exact-head CI #682 полностью зелёный: backend/PostgreSQL concurrency rehearsal, frontend, dependency-security и browser-smoke.

Следующий Data hardening slice — IANA timezone storage и DST-correct recurring Activity wall-clock semantics.

## [0.6.21-alpha.2] — 2026-09-21

Hotfix — mobile routed-content visibility + unique session JWTs.

- исправлен mobile regression из `0.6.21-alpha.1`: RouterView transition теперь анимирует стабильную DOM-обёртку, а не произвольный component root/fragment, поэтому shell больше не может остаться без routed content;
- browser-smoke теперь явно проверяет видимость главного заголовка Space Discovery после registration, full reload/refresh recovery и повторного login;
- access/refresh JWT получают уникальный `jti` и `iat`, поэтому несколько token issuance для одного Account в одну секунду больше не создают одинаковые refresh tokens и не конфликтуют с `user_devices.token`;
- добавлены contract tests на uniqueness back-to-back access/refresh tokens;
- Firefox logout path в browser-smoke использует keyboard activation после accessibility assertions, исключая старый pointer timing flake;
- functional exact-head CI #662 полностью зелёный: backend, frontend, dependency-security и Chromium/Firefox/WebKit/mobile browser-smoke.

## [0.6.21-alpha.1] — 2026-09-21

Stage 6 checkpoint 13 — UI motion/loading polish.

- RouterView получил мягкий out-in transition и delayed/min-visible navigation progress, чтобы быстрые маршруты не мигали, а lazy/data-heavy переходы имели понятный feedback;
- добавлены общие motion/state/popover/skeleton/spinner primitives с корректным `prefers-reduced-motion`;
- Create Space modal теперь плавно открывает backdrop/panel, на mobile ведёт себя как sheet, блокирует body scroll и показывает pending spinner при submit;
- persona dropdown и chevron получили плавное состояние открытия/закрытия;
- Messenger больше не показывает ложное empty-state до загрузки: добавлены skeleton списка, skeleton истории, error/retry и pending state открытия разговора;
- registration step, profile settings, Space discovery loading/error/results/empty и join actions получили мягкие transitions/pending feedback;
- login/profile/registration submit-кнопки показывают явный spinner/pending state;
- восстановлен корневой `update.sh` wrapper, делегирующий routine production update в `ops/deploy.sh`;
- functional exact-head CI #645 fully green: backend, frontend, dependency-security и Chromium/Firefox/WebKit/mobile browser-smoke.

Motion не должен замедлять приложение искусственно: progress появляется только после короткой задержки, а reduced-motion users получают практически мгновенные состояния.

## [0.6.20-alpha.1] — 2026-09-21

Stage 6 checkpoint 12 — browser/security launch gate.

- browser runtime contract теперь same-origin по умолчанию: SPA использует `/api`, а Vite dev/preview proxy передаёт HTTP и WebSocket трафик в backend без исторического `http://localhost:9000` fallback;
- CSRF усилен с cookie-only проверки до signed HttpOnly cookie + отдельного `X-CSRF-Token` proof, который SPA хранит только в памяти;
- unsafe API requests сами выполняют CSRF bootstrap, поэтому registration/login/refresh больше не зависят от mount-time race;
- full reload восстанавливает session через HttpOnly refresh cookie + новый CSRF proof, не записывая access token в local/session storage;
- добавлен Playwright launch gate для Chromium, Firefox, WebKit/Safari-compatible engine и narrow mobile Chromium;
- browser journey реально выполняет registration → refresh-after-reload → Messenger route → logout/revocation → login и проверяет cookie/session semantics;
- CI запрещает возврат cross-origin localhost API fallback в SPA source;
- production dependency gate теперь запускает `npm audit --omit=dev --audit-level=high` и `pip-audit`;
- frontend production lock обновлён до audit-clean набора; direct floors подняты для Axios, DOMPurify и UUID;
- backend security-sensitive dependencies обновлены; FastAPI/Starlette закреплены на audit-clean совместимой паре, сохраняющей текущий route contract;
- функциональный exact-head CI #637 полностью зелёный: dependency-security, frontend, backend/PostgreSQL/Redis/Sentinel/recovery и четыре browser projects.

Этот checkpoint закрывает автоматизированный desktop/WebKit auth/session launch gate, но не подменяет реальный iOS/iPadOS installed-PWA/device rehearsal и оставшиеся pre-beta performance/accessibility/production-data задачи.

## [0.6.19-alpha.1] — 2026-09-21

Stage 6 checkpoint 11 — privacy-safe external delivery observability baseline.

- email/Web Push получили агрегированные operational metrics по durable `external_delivery_ledger`: pending/due backlog, processing, expired claims, retry pressure, delivered/failed и failure classes;
- stale due backlog определяется отдельными alert thresholds для email и Web Push, не меняющими delivery behavior;
- admin-only endpoint `GET /admin/operations/external-delivery` отдаёт только агрегаты;
- standalone CLI `python -m workers.external_delivery_observability` печатает machine-readable report и поддерживает `--require-healthy` для внешнего monitoring;
- email queue/delivery и Web Push delivery workers получили structured JSON completion events;
- structured logger fail-closed отклоняет sensitive field names для tokens/secrets/passwords/destination email/push endpoints/key material/message body/content;
- PostgreSQL integration проверяет stale backlog + expired claim detection и отсутствие Account ID, aggregate/dedupe keys, claim token и provider id в metrics output;
- CI теперь отдельно запускает observability CLI machine gate;
- функциональный exact-head CI #608 прошёл frontend/backend, migrations/schema drift, PostgreSQL observability rehearsal, Redis/Sentinel, multi-process WebSocket, rolling reload, legacy migration и backup/restore.

Этот checkpoint закрывает ledger-side external-delivery visibility, но не объявляет готовым полный observability stack: provider-side SLA telemetry, общий HTTP/realtime/Redis/PostgreSQL metrics backend, error tracking и pager/on-call остаются отдельной pre-beta работой.

## [0.6.18-alpha.1] — 2026-09-21

Stage 6.8 checkpoint 9 — protective-hold shadow calibration and moderation storage lifecycle gate.

- protective holds получили явные режимы `off | shadow | enforce`; default остаётся `off`;
- `shadow` вычисляет would-hold решение и пишет privacy-minimal evaluation, но никогда не меняет user capabilities;
- добавлен durable `protective_hold_evaluations` ledger без message body, attachment URL, recipient list или Persona handle;
- moderator queue получила явные human labels `true_positive / false_positive / unclear`, не создающие restriction;
- aggregate calibration считает false-positive rate отдельно для DM burst и invite burst, а также ограниченный confirmed-candidate capture proxy;
- enforce fail-closed: каждый signal family должен набрать минимум human-labeled candidates и пройти FP threshold, после чего всё равно требуется отдельный `MODERATION_PROTECTIVE_HOLD_ENFORCEMENT_APPROVED=true`;
- legacy `MODERATION_PROTECTIVE_HOLDS_ENABLED=true` больше не является достаточным условием для санкции;
- standalone calibration CLI умеет печатать отчёт и завершаться non-zero, если data gate не готов;
- moderator operations dashboard показывает automation mode, calibration readiness/FP и storage-lifecycle status;
- private moderation evidence backup/snapshot retention теперь должен быть явно объявлен; production preflight отклоняет отсутствующие значения и сроки, превышающие application retention;
- retention-worker installer требует storage lifecycle declarations до включения timer;
- CI отдельно rehearses shadow-without-sanction, false-positive gate, approval gate, allow-listed enforcement и storage retention preflight;
- synthetic CI labels проверяют механику, но **не считаются production calibration data**.

Реальное включение protective holds после этого checkpoint всё ещё требует накопления human-reviewed production-like/production shadow data. Preflight также не настраивает provider lifecycle автоматически: заявленные backup/snapshot сроки должны соответствовать фактической инфраструктуре.

## [0.6.17-alpha.1] — 2026-09-21

Stage 6.8 checkpoint 8 — bounded private moderation evidence retention and application-level secure expiry.

- `moderation_media_records` получил durable `retention_due_at` / `purged_at` lifecycle и nullable file-locating metadata после expiry;
- removed evidence получает configurable retention baseline: 90 дней по умолчанию, жёстко ограниченный 7–365 днями;
- фактический expiry гарантирует полный retention window после самой поздней точки `removed_at`, final report resolution или завершения связанной restriction appeal;
- active Trust & Safety report и pending appeal блокируют deletion; deferred records фильтруются до bounded batch selection, чтобы они не starvation-или eligible evidence;
- private storage обязан быть disjoint от публичного `/uploads`; quarantine directory/file hardening использует 0700/0600, worker — `UMask=0077`;
- retention deletion confined к каталогу конкретного `record.uid`, включая запрет sibling-record traversal;
- expiry удаляет private bytes, scrub-ит private/original path, URL, filename и MIME metadata, но сохраняет moderation decision/reason/audit linkage;
- missing file на retry является idempotent recoverable state; worker завершает metadata scrub и audit outcome `already_missing`;
- отдельный systemd oneshot/timer запускает bounded `FOR UPDATE SKIP LOCKED` cleanup вне Uvicorn lifecycle;
- moderator operations metrics показывают только aggregate due/purged counts и configured retention days;
- документация явно отделяет application-level expiry от forensic secure wipe на SSD/COW/snapshots/backups;
- functional exact-head CI #595 green: frontend/backend contracts, PostgreSQL retention lifecycle, Redis/Sentinel, multi-process WebSocket, rolling reload, legacy migration и backup/restore.

Protective holds остаются выключенными по умолчанию. Следующий Trust & Safety шаг — production calibration на human-reviewed signals и согласование backup/snapshot lifecycle с утверждённой evidence retention policy.

## [0.6.16-alpha.1] — 2026-09-20

Stage 6.8 checkpoint 7 — Trust & Safety operations metrics, incident rehearsal and calibrated protective-hold baseline.

- добавлен privacy-minimal aggregate endpoint `/trust-safety/v1/metrics`: queue age, average decision time, appeal overturn rate, AI outcomes, behavioral-signal backlog и human/automation restriction origins без Account ID или содержимого жалоб;
- moderator UI показывает operational dashboard и текущий безопасный policy-status protective holds;
- protective holds существуют как отдельный low-risk automation path, но **выключены по умолчанию** до калибровки human-reviewed false-positive rate;
- один behavioral signal никогда не создаёт sanction: для hold нужны минимум два отдельных high/critical server-owned signal bucket в bounded lookback;
- automation allow-list ограничен только `messenger.send` и `invitation.send`; срок всегда 5–15 минут, permanent restriction невозможен;
- `account.access`, Space chat, media actions, profile/discovery powers, revoke и appeal decisions не входят в automation surface;
- privileged Account с platform authority исключён из automation path;
- Account-level `FOR UPDATE` сериализация не позволяет concurrent detectors создать дублирующий hold; каждое действие имеет audit event и может быть снято обычным human revoke/appeal path;
- provider outage AI-copilot отдельно rehearsed: failure аудируется, recommendation/restriction не создаются, claim state не меняется;
- добавлен `docs/trust-safety-incident-rehearsal-v1.md` с incident matrix и beta gate;
- functional exact-head CI #579 прошёл frontend/backend/PostgreSQL/Redis/Sentinel/WebSocket/legacy migration/backup-restore gates до release-doc sync.

Следующий отдельный Trust & Safety slice — формальная privacy-retention/secure-expiry policy для private moderation evidence и production calibration до возможного включения protective holds.

## [0.6.15-alpha.1] — 2026-09-20

Stage 6.8 checkpoint 6 — reversible reported-media moderation workflow.

- добавлен отдельный permission `moderation.platform.media.manage` для quarantine/restore/remove действий над пожалованными вложениями;
- `moderation_media_records` хранит durable audit-oriented state без публикации private evidence path клиенту;
- quarantine переносит локальный `/uploads` файл в приватное moderation storage и помечает attachment metadata server-side;
- restore возвращает файл и снимает moderation marker; remove оставляет его вне публичной выдачи, сохраняя evidence copy до применения retention policy;
- filesystem move поддерживает cross-device deployment и compensating rollback при ошибке DB commit;
- path confinement запрещает traversal и внешние URL;
- действия требуют claim ownership, explicit permission и authority выше target Account; AI/automation не получают punitive media authority;
- moderator UI показывает reported attachments и даёт явные quarantine/restore/remove controls с причиной действия;
- PostgreSQL/filesystem integration и contract tests покрывают reversible state, audit и cross-filesystem fallback.

## [0.6.14-alpha.1] — 2026-09-18

Stage 6.8 checkpoint 5 — privacy-minimal anti-spam / raid abuse signals.

- добавлен durable `trust_safety_abuse_signals` ledger для behavioral evidence без хранения message body, private-dialog transcript или attachment URLs;
- realtime Messenger/Space rate-limit pressure создаёт deduped advisory signal, но не автоматическую санкцию;
- Messenger detector отслеживает burst по distinct DM recipients в bounded window как признак массовых нежелательных контактов;
- Space invitation detector отслеживает burst по distinct invitees в bounded window как признак invite spam;
- thresholds/window/dedupe параметры конфигурируемые и ограничены безопасными минимумами;
- moderator API и Trust & Safety UI получили отдельную очередь behavioral signals со статусами open/reviewed/dismissed;
- review/dismiss signal не создаёт restriction и не меняет Account permissions: punitive path остаётся только human moderation flow;
- PostgreSQL integration проверяет durable dedupe/upsert, human review state и отсутствие side-effect restriction;
- Alembic/model registry/schema-drift интеграция синхронизирована.

## [0.6.13-alpha.1] — 2026-09-18

Stage 6.8 checkpoint 4 — provider-neutral moderation AI copilot.

- добавлен отдельный permission `moderation.platform.ai.assess`; доступ к Trust & Safety queue сам по себе не даёт права использовать AI provider;
- AI-copilot работает только с жалобой, уже взятой модератором в claim, и не имеет punitive authority;
- provider-neutral `http_json` adapter принимает строго структурированный assessment и валидирует ответ через Pydantic schema;
- provider payload privacy-minimal: только пожалованный Persona/message object; без Account UID, handle, sender/recipient identity, истории личного диалога, attachment URL и свободного текста описания жалобы;
- `account.access` исключён из AI suggestion schema; AI может предложить только bounded temporary restriction или отсутствие санкции;
- durable `moderation_ai_recommendations` хранит category/severity/confidence/summary/rationale и human outcome, но не raw prompt, raw provider response, chain-of-thought или private conversation history;
- на одну жалобу действует bounded assessment budget, по умолчанию 3 запроса, чтобы исключить бесконтрольное provider-cost amplification;
- moderator UI показывает AI severity/confidence/summary/rationale и позволяет явно принять предложение как черновик, взять его за основу для изменения либо отклонить; применение restriction всё равно идёт через обычный human moderation API и hierarchy/permission checks;
- provider failure аудируется и не меняет moderation state;
- Alembic/model registry синхронизированы; deterministic contract tests и PostgreSQL integration покрывают schema/privacy/persistence/audit/human-outcome boundaries.

## [0.6.12-alpha.1] — 2026-09-17

Stage 6.8 checkpoint 3 — fine-grained platform moderation permission hierarchy.

- доступ к Trust & Safety queue больше не означает автоматическое право выдавать, снимать и пересматривать санкции: добавлены отдельные `moderation.platform.restrict`, `moderation.platform.revoke` и `moderation.platform.appeal.review` permissions;
- baseline moderator получает обычные issue/revoke/appeal-review powers, а permanent restrictions и `account.access` по-прежнему требуют отдельных elevated permissions;
- restriction issuance требует одновременно platform moderation access, explicit issue permission и строгий `actor_authority > target_authority`;
- direct revoke требует отдельный revoke permission, authority выше target и authority не ниже snapshot исходного issuer, поэтому peer moderator не может отменить sanction более сильного admin;
- revoke permanent restriction и `account.access` дополнительно требует тех же elevated permissions, что нужны для чувствительного исходного решения;
- appeal review требует отдельного review permission плюс существующие authority/sensitivity checks; independent-review search учитывает только реально eligible reviewers;
- action endpoints переведены с generic moderator dependency на specific action dependencies, а capability discovery возвращает только те capabilities, которые текущий moderator действительно может выдать;
- миграция `k0a6d4f88010` после исторического explicit-ID seed синхронизирует sequence `platform_permissions_id_seq`, устраняя collision при clean migration;
- PostgreSQL integration проверяет denial для manage-only custom role, peer-moderator revoke, запрет override admin sanction, elevated permanent/account-access permissions и explicit appeal-review permission;
- moderator UI использует server-provided permission flags, чтобы не предлагать actor действия, которые backend всё равно отклонит.

Следующий Stage 6.8 slice — provider-neutral AI assessment / copilot layer; punitive authority остаётся только у human policy path.

Quality gate: functional exact-head CI #528 green before release-doc sync; final exact-head CI required before merge.

## [0.6.11-alpha.1] — 2026-09-17

Stage 6.8 checkpoint 2 — end-to-end `account.access` platform suspension.

- сильнейшая moderation capability `account.access` переведена из schema-only состояния в реальный server-side enforcement и разрешена только в platform scope;
- выдача suspension по-прежнему требует `moderation.platform.account_access`, обычного platform moderation permission и строгого `actor_authority > target_authority`;
- при выдаче ограничения существующие Identity v2 sessions отзываются в той же транзакции, legacy device sessions деактивируются;
- короткоживущий stateless access JWT не позволяет обойти suspension: каждый authenticated HTTP request повторно проверяет durable PostgreSQL restriction;
- доступ под suspension ограничен минимальным Safety-контуром: identity bootstrap, просмотр собственного ограничения, создание/просмотр своей апелляции и logout;
- login/refresh могут создать restricted session, чтобы Account не терял право узнать причину санкции и подать апелляцию;
- realtime ticket re-check выполняется после consume one-time ticket, закрывая гонку «ticket выдан непосредственно перед suspension»;
- уже открытые Messenger/Space WebSocket соединения отключаются distributed `account_control` событием во всех Uvicorn workers; Redis transport failure не отменяет durable sanction;
- SPA получила отдельный restricted Safety Center с причиной, сроком, appeal state и logout вместо доступа к обычным функциям PubChat;
- снятие/истечение restriction не восстанавливает ранее отозванные sessions: Account проходит нормальную повторную аутентификацию;
- PostgreSQL integration и contract tests фиксируют platform-only scope, session revocation, active/revoke semantics, узкий HTTP exemption surface и HTTP/realtime enforcement hooks.

Следующий отдельный Trust & Safety task — hardening moderation hierarchy/permissions; AI-assessment остаётся последующим этапом после human authority path.

Quality gate: exact-head CI #524 green before merge.

## [0.6.10-alpha.1] — 2026-09-17

Stage 6.8 checkpoint 1 — production-grade Trust & Safety foundation.

- platform Trust & Safety intake отделён от Space-local moderation и принимает Persona, received Messenger message и Space message reports;
- server-owned priority, duplicate/rate guard, moderator queue claim/release и privacy-bounded evidence access фиксируют операционный report flow;
- evidence viewing и решения пишутся в append-only audit trail, а пользователь получает понятный public explanation;
- platform roles получили authority levels (`user=0`, `moderator=50`, `admin=100`), а санкции требуют одновременно permission и `actor_authority > target_authority`;
- добавлены durable Account-level capability restrictions с platform/Space scope, temporary/permanent duration, authority snapshots и revoke history;
- permanent restrictions и полный `account.access` требуют отдельных elevated permissions;
- server-side enforcement подключён для `messenger.send`, `space.chat.send`, `media.upload`, `space.create`, `space.join`, `invitation.send`, `profile.edit` и `discovery.publish`;
- restriction API не предлагает capabilities без реального backend enforcement;
- Safety Center показывает Account его ограничения, причину, scope и expiry;
- platform-restriction appeals имеют отдельную queue, claim/release, authority checks и independent-review preference; overturn revoke-ит restriction, не стирая историю;
- moderator Trust & Safety UI поддерживает report triage, evidence, restriction issue/revoke и appeal review;
- AI-copilot boundary зафиксирован документально: AI помогает triage/evidence/recommendation, но не имеет punitive authority в beta baseline.

`account.access` в этом checkpoint ещё намеренно не выдавался до появления полного session/HTTP/realtime enforcement; это закрыто в `0.6.11-alpha.1`.

Quality gate: exact-head CI → release sync → exact-head CI перед merge.

## [0.6.9-alpha.1] — 2026-09-16

Stage 6 checkpoint 10 — Web Push / PWA Messenger delivery.

- добавлена Account-owned per-device модель `web_push_subscriptions` с endpoint fingerprinting и lifecycle API для register/status/remove;
- Web Push остаётся явным opt-in: browser permission запрашивается только после действия пользователя и никогда не появляется при bootstrap приложения;
- VAPID private key хранится только на backend; клиент получает только public key и capability status;
- offline push queue создаётся только для Messenger и только когда получатель offline; Space chat по-прежнему не создаёт background push pressure;
- push payload privacy-minimal: без текста личного сообщения, sender identity и иных данных переписки; click destination ограничен same-origin Messenger route;
- перед network delivery повторно проверяются Redis presence, текущий opt-in, unread state и Account block/privacy;
- Web Push использует тот же durable `external_delivery_ledger`: per-conversation cooldown/dedupe, `FOR UPDATE SKIP LOCKED`, expiring claim lease и bounded retry/backoff;
- terminal provider responses `404/410` удаляют протухшие subscriptions; retryable failures остаются bounded;
- push worker вынесен в отдельные systemd oneshot/timer units и не живёт внутри Uvicorn lifecycle;
- logout/session teardown инвалидирует local PushSubscription, чтобы shared browser/device не продолжил получать уведомления предыдущего Account;
- service worker получил `push`/`notificationclick`, сохранив static-only cache contract: auth/API/private data по-прежнему не кэшируются;
- Notifications UI получил email/Web Push preference controls и explicit device opt-in flow;
- добавлены migration `k0a6d4f88006`, deterministic Web Push privacy/provider/endpoint tests и PWA regression guard;
- functional exact-head CI прошёл migration/schema/backend/PostgreSQL/Redis Sentinel/multiprocess/rolling-deploy/frontend gates перед release-doc sync.

Следующий launch-critical workstream — production-grade moderation / Trust & Safety end-to-end flow; параллельно продолжаются browser/security/observability gates и формализация unit economics/monetization boundaries.

Quality gate: functional exact-head CI → version/docs sync → повторный exact-head CI перед merge.

## [0.6.8-alpha.1] — 2026-09-16

Stage 6 checkpoint 9 — durable unread-Messenger email delivery.

- добавлен privacy-minimal `external_delivery_ledger`: durable status/retry/provider metadata, aggregate counts и dedupe keys без текста личных сообщений и без сохранения email destination в ledger;
- scheduled candidate worker выбирает только давно отсутствующие Account с unread Messenger, подтверждённым email и явным `email_unread_dm_nudge` opt-in;
- Redis presence проверяется до queue и непосредственно перед delivery; вернувшийся online Account не получает offline nudge и не расходует retry budget;
- Account block/privacy повторно проверяются перед queue/delivery, при этом legacy `PrivateMessage`/`RoomMember` UIDs явно сопоставляются через `Account.legacy_user_uid`;
- Account-level cooldown не обходится новым входящим DM: внешний re-engagement остаётся периодическим агрегированным напоминанием, а не письмом на каждое сообщение;
- SMTP adapter поддерживает STARTTLS/implicit SSL, privacy-safe plain/HTML template, stable RFC Message-ID и разделение retryable/terminal provider failures;
- delivery worker использует PostgreSQL `FOR UPDATE SKIP LOCKED`, expiring claim lease и bounded exponential backoff; stale opt-out/read/block state переводит запись в `suppressed`;
- worker claim-ит только непосредственно обрабатываемую запись, чтобы длинный SMTP batch не позволял lease более поздних записей истечь до отправки;
- добавлены CLI queue/deliver/all stages, отдельные systemd oneshot/timer и installer с security/realtime/SMTP preflight;
- PostgreSQL integration test проверяет disjoint concurrent claims и recovery expired lease;
- добавлен `docs/message-email-delivery-v1.md` с production/retry/privacy контрактом и явной оговоркой, что SMTP не даёт абсолютный exactly-once после crash-after-send;
- все существующие PostgreSQL/Redis Sentinel/recovery, multi-process WebSocket, rolling deploy и frontend gates остаются зелёными.

Следующий Stage 6.3 slice: standards-based Web Push/PWA delivery и notification permission/subscription UX; параллельно продолжаются browser/security/observability gates.

Quality gate: functional exact-head CI → version/docs sync → повторный exact-head CI перед merge.

## [0.6.7-alpha.1] — 2026-09-16

Stage 6 checkpoint 8 — message notification policy / active context baseline.

- добавлены account-level настройки Messenger/Space in-app уведомлений и звуков, а также opt-in flags для будущих email/Web Push adapters;
- Messenger active context хранится как connection-scoped TTL state в Redis и обновляется heartbeat/reconnect;
- Space active context использует уже существующий distributed room presence contract;
- server-side delivery policy подавляет дублирующий toast/sound, когда получатель уже смотрит тот же conversation/Space, не меняя authorization/message delivery;
- offline external re-engagement разрешён только для Messenger и только по opt-in; Space chat для offline Account не создаёт background notification pressure;
- Space alert fan-out ограничен active membership, online presence и Account block boundaries;
- SPA объединяет Messenger/Space message alerts и использует существующие `private_notification.mp3` / `chat_notification.mp3`;
- добавлена Alembic migration `k0a6d4f88004` и API для чтения/изменения message notification preferences;
- deterministic tests фиксируют online/offline/active-context policy и active-context lifecycle;
- Redis Sentinel/restart recovery, multi-process WebSocket, production rolling deploy, PostgreSQL migration/recovery и frontend gates остаются зелёными.

Durable email delivery ledger, scheduled unread-DM nudge worker, provider retry/backoff и Web Push остаются следующими Stage 6.3 slices.

Quality gate: functional CI → version/docs sync → повторный exact-head CI перед merge.

## [0.6.6-alpha.1] — 2026-09-16

Stage 6 pre-beta hardening checkpoint 7 — Redis Sentinel failover/capacity baseline.

- добавлен backward-compatible Redis topology layer: direct `REDIS_URL` и Redis Sentinel master discovery;
- Sentinel mode поддерживает отдельные master/Sentinel credentials, DB, timeout и peer-validation settings;
- `RealtimeService` больше не привязан к фиксированному master host и создаёт command/PubSub connections через failover-aware pool;
- production deploy preflight принимает direct или complete Sentinel configuration и отклоняет частично заданную topology config;
- CI поднимает реальный Redis master + replica + три Sentinel process с quorum `2`;
- текущий master реально останавливается, Sentinel promotes replica, а те же `RealtimeService` objects восстанавливают ticket issue/consume без restart application process;
- PubSub subscription автоматически пересоздаётся через promoted master и снова принимает события;
- bounded concurrent ticket bursts проверяются до и после promotion как correctness/capacity baseline без искусственных throughput-обещаний;
- restart recovery, multi-process WebSocket, rolling deploy, PostgreSQL migration/recovery и frontend gates остаются зелёными.

Redis остаётся ephemeral realtime слоем: failover не делает one-time tickets, presence или pub/sub durable. Durable message/history/membership state остаётся в PostgreSQL.

Следующий активный Stage 6 workstream: notification/message delivery hardening (online/offline policy, active-context suppression, unread-Messenger email nudge и Web Push), параллельно с observability/security/browser gates.

Quality gate: real Sentinel promotion CI → main sync → version/docs sync → повторный exact-head CI перед merge.

## [0.6.5-alpha.2] — 2026-09-16

Stage 6 parallel stabilization checkpoint — production deploy reliability + messaging UX polish.

- production backend переведён на Uvicorn multiprocess supervisor с минимум двумя workers при `DEBUG=False`;
- systemd владеет постоянным listener `127.0.0.1:9000` через `pubchat-backend.socket`, поэтому supervisor restart не создаёт connection-refused окно для nginx;
- routine deploy использует `SIGHUP` rolling worker reload вместо остановки единственного listener;
- добавлены `/health/live` и dependency-aware `/health/ready` для PostgreSQL + production Redis;
- tracked deploy script выполняет security/Redis preflight, migrations, staged frontend build, rolling reload и readiness gate;
- SPA build сначала собирается в `dist.next`, затем публикует static/hash assets и только после них `index.html`, не очищая live build во время сборки;
- CI реально проверяет inherited persistent socket, SIGHUP worker replacement и queued HTTP request во время полного supervisor replacement без connection-refused;
- authenticated SPA bootstrap повторяет transient network/`502`/`503`/`504` ошибки с bounded backoff;
- Space chat и Messenger получили compact messaging UX pass: attachment shelf, более плотный composer, calmer message chrome и responsive controls;
- desktop Space info panel больше не показывает overlay-only close control на широком layout.

Это patch checkpoint внутри `0.6.5`: следующий инфраструктурный Stage 6.2 checkpoint остаётся Redis failover topology/capacity.

Quality gate: production-deploy/realtime/frontend functional CI → version/docs sync → повторный exact-head CI перед merge.

## [0.6.5-alpha.1] — 2026-09-16

Stage 6 pre-beta hardening checkpoint 6 — bounded WebSocket backpressure.

- каждый process-local WebSocket имеет отдельную bounded outbound queue;
- Redis/pub-sub fan-out больше не ждёт socket write каждого клиента и только ставит frame в локальную очередь;
- один sender task на socket сохраняет порядок кадров;
- переполнение очереди изолированно отключает только медленного клиента с WebSocket code `1013`;
- socket send timeout также изолирует stalled consumer и не задерживает delivery другим соединениям;
- лимит очереди настраивается через `REALTIME_OUTBOUND_QUEUE_SIZE` (default `64`);
- deterministic tests проверяют порядок, non-blocking overflow и send-timeout isolation;
- все PostgreSQL/Redis recovery, multi-process rolling-restart и frontend gates остаются зелёными.

Остаётся Stage 6.2 задача: Redis failover topology/capacity tests. Общий load/capacity profiling продолжается также в performance/operations блоках Stage 6.

Quality gate: functional exact-head CI → version/docs sync → повторный exact-head CI перед merge.

## [0.6.4-alpha.1] — 2026-09-16

Stage 6 pre-beta hardening checkpoint 5 — real multi-process WebSocket / rolling-restart baseline.

- CI поднимает два отдельных Uvicorn/FastAPI process против общих PostgreSQL и Redis;
- one-time realtime ticket выдаётся вне worker process и consume-ится внутри конкретного WebSocket worker;
- distributed presence виден между процессами через Redis;
- Redis pub/sub доставляет user event в worker, который владеет process-local WebSocket object;
- один Uvicorn process останавливается как часть rolling restart, в то время как второй продолжает обслуживать realtime traffic;
- после запуска replacement process клиент подключается заново с новым one-time ticket и снова получает realtime события;
- существующие PostgreSQL migration/recovery, Redis restart/recovery и frontend gates продолжают проходить в том же pipeline;
- добавлен `docs/realtime-multiprocess-v1.md`.

Остаются Stage 6.2 задачи: slow-client/backpressure под нагрузкой и Redis failover topology/capacity tests.

Quality gate: functional exact-head CI → version/docs sync → повторный exact-head CI перед merge.

## [0.6.3-alpha.1] — 2026-09-16

Stage 6 pre-beta hardening checkpoint 4 — Redis restart/recovery.

- CI намеренно останавливает Redis 7.2 service container;
- при `DEBUG=False` outage обязан проявляться как `RealtimeUnavailable`, process-local fallback запрещён;
- Redis запускается снова в том же CI job;
- те же, уже созданные `RealtimeService` objects восстанавливают ticket issue/consume без restart Python process;
- pub/sub listener автоматически пересоздаёт subscription после Redis restart;
- cleanup гарантированно возвращает Redis в рабочее состояние даже при падении assertion;
- PostgreSQL migration/recovery и frontend gates продолжают проходить в том же pipeline;
- добавлен `docs/redis-recovery-v1.md`.

Ephemeral Redis keys (presence, unconsumed tickets, TTL counters, transient pub/sub) не превращаются в durable state: после outage протокол восстанавливает transport/reconnect там, где это нужно.

Остаются Stage 6.2 задачи: реальные multi-process WebSocket/Uvicorn scenarios, rolling-restart client reconnect, slow-consumer/backpressure/load и Redis failover topology.

Quality gate: functional exact-head CI → version/docs sync → повторный exact-head CI перед merge.

## [0.6.2-alpha.1] — 2026-09-16
Stage 6 checkpoint 3 — Redis 7.2 production-semantics baseline: distributed one-time tickets/TTL, presence, rate limits, idempotency и cross-instance protocol-v2 pub/sub при `DEBUG=False`.

## [0.6.1-alpha.1] — 2026-09-16
Stage 6 checkpoint 2 — PostgreSQL 16 backup/restore recovery drill: portable custom-format dump, restore в отдельную DB, Alembic head/zero drift и повторные semantic legacy assertions.

## [0.6.0-alpha.1] — 2026-09-16
Stage 6 checkpoint 1 — PostgreSQL 16 clean historical migration, `alembic check`, async integration, representative legacy-data rehearsal, DB URL hardening и explicit ORM registry для standalone processes.

## [0.5.5-alpha.1] — 2026-09-16
Stage 5.6 — installable PWA shell, static-only service-worker cache, external reminder worker с durable cursor и centralized notification lifecycle.

## [0.5.4-alpha.1] — 2026-09-15
Stage 5.5 — explainable organic Space discovery: eligibility-first ranking, server-only score, organic activity/context signals и no-paid/no-gift boundary.

## [0.5.3-alpha.1] — 2026-09-15
Stage 5.4 — consent-first internal gifts, append-only support ledger, cosmetic entitlements и Persona/Space support UI без real-money flows.

## [0.5.2-alpha.1] — 2026-09-15
Stage 5.3 — bounded Activity Occurrences, opt-in reminders, private notification inbox и idempotent reconciliation.

## [0.5.1-alpha.1] — 2026-09-15
Stage 5.2 — system-earned achievements и Activity Conversation Rounds без score/winner/prize/stake.

## [0.5.0-alpha.1] — 2026-09-15
Stage 5.1 — Persona/Space appearance, recurring Activities, RSVP и mobile-first product identity UI.

## [0.4.0-alpha.1] — 2026-09-15
Stage 4 — canonical Living Spaces, memberships/scoped roles, social graph, invitations, Rules/Events/History и transparent moderation/appeals.

## [0.3.0-alpha.1] — 2026-09-15
Stage 3 — Realtime v2: one-time WebSocket tickets, Redis pub/sub/presence, heartbeat/reconnect, rate limits/idempotency и memory-only browser access JWT.

## [0.2.0-alpha.1] — 2026-09-15
Stage 2 — Identity v2: Account/Persona/Credential/Session/Privacy, RBAC и Persona-first SPA shell.

## [0.1.0-alpha.1] — 2026-09-15
Stage 1 — revival foundation/security: server-side admin authorization, IDOR/mass-assignment fixes, secret/token logging hardening, DB health check и CI.

## [0.0.0-alpha.0] — legacy baseline
Исходное состояние старого проекта до revival. Историческая точка отсчёта, не рекомендуемый релиз.

Подробные технические контракты находятся в `docs/README.md`, `docs/roadmap.md` и профильных `docs/*`.