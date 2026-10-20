# Живой статус реализации PubChat: Web / Android / iOS

> Срез подтверждён **19 октября 2026 г.** по состоянию репозиториев и GitHub PR/Issues. Эта таблица — **реестр реализованных пользовательских сценариев**, а не обещание готовности 1.0. При каждом изменении сначала сверять актуальные ветки и PR. История релизов — в [CHANGELOG](../CHANGELOG.md), план — в [roadmap](roadmap.md).

## Источники и принципы

- Сервер/Web: [cyrox007/PubChat](https://github.com/cyrox007/PubChat) (`main`). Android: [cyrox007/PubChat-Android](https://github.com/cyrox007/PubChat-Android) (`master`). iOS: [cyrox007/PubChat-iOS](https://github.com/cyrox007/PubChat-iOS) (`main`).
- Основные продуктовые задачи: [Social Core #107](https://github.com/cyrox007/PubChat/issues/107), [Social/DM parity #110](https://github.com/cyrox007/PubChat/issues/110), [Android functional parity #52](https://github.com/cyrox007/PubChat-Android/issues/52).
- **Код / CI / устройство / релиз — разные статусы.** Зелёный simulator, Gradle, Playwright или backend contract не заменяют реальный Android/iPhone. Отсутствие проверки устройства значит «device QA не подтверждён», а не «не реализовано».
- Любой отказ `401/403/409`, privacy/block/permission, E2EE policy определяется сервером; клиенты обязаны обрабатывать его без обхода и без plaintext downgrade.
- Account владеет сессиями, отношениями и санкциями; Persona — публичное представление. Вторичные Persona не образуют независимых графов или DM-правил.
- Любой статус «слит/завершён» должен иметь **ссылку на merge commit/PR и тесты**, а не только ссылку на feature branch.

## Функциональная матрица (факт на указанный срез)

| Пользовательский сценарий | Web / сервер | Android | iOS | Что ещё блокирует приёмку |
| --- | --- | --- | --- | --- |
| Регистрация, вход, refresh/logout | Есть Identity v2 | Код | Код | Сценарии отказов/сессий на реальных устройствах |
| Private Multi-Persona: создать, выбрать | Сервер/Web [#108](https://github.com/cyrox007/PubChat/pull/108) | Слито [#35](https://github.com/cyrox007/PubChat-Android/pull/35) | Слито [#3](https://github.com/cyrox007/PubChat-iOS/pull/3) | Публичная адресация, attribution, cross-Persona privacy и device QA **не готовы** |
| Подписки, друзья, блокировки | API + Web | Код, friendship hub [#36](https://github.com/cyrox007/PubChat-Android/pull/36) | Код, friendship hub [#4](https://github.com/cyrox007/PubChat-iOS/pull/4) | 401/403/409, block/revocation, реальное взаимодействие устройств |
| People discovery / кратковременная availability | Поиск, intent, server TTL | Код/UI | Код/UI | Одинаковое поведение ошибок, пагинация и device QA |
| Согласие на новые DM: четыре политики | `/identity/v2/privacy`, enforcement | **Слито [PR #53](https://github.com/cyrox007/PubChat-Android/pull/53), `7160c5d`**, обе Android CI-конфигурации green | [PR #16](https://github.com/cyrox007/PubChat-iOS/pull/16) слит, simulator CI green | Device QA обоих клиентов, cross-client проверка создания DM после revoke/block и 401/403/409 |
| Каталог Spaces, membership, room/realtime | Код | Код | Каталог; участие/realtime не завершены | Native cross-client round-trip |
| **Создать Space** (тип, доступ, категории, join policy, лимит, теги) | Реальный API `POST /spaces/v1` | **Слито [PR #51](https://github.com/cyrox007/PubChat-Android/pull/51), `05653df`** | UI/API отсутствует | На Android нужен physical QA; следующий перенос этого сценария на iOS |
| Space invitations: увидеть, принять/отклонить, войти | Web + API | [Android PR #56](https://github.com/cyrox007/PubChat-Android/pull/56) **слит**, `07cae34`, обе Android CI-конфигурации green: inbox + accept/decline + server-confirmed entry | Нет завершённого flow | **Не подтверждена** физическая Android QA, Web↔Android privacy/expired/revoked/invite-only; iOS ещё требует реализацию |
| Activities / события, повторы, напоминания | Web/API | Частичная панель событий | Нет полного flow | Нативные повторения, участие, уведомления, DST |
| Messenger: чат, отправка, реакции и медиа | Web/API | Базовые действия в коде | Неполный messenger | Нативная безопасность, retry/network и privacy |
| **E2EE DM** | Web E2EE policy + HTTP no-downgrade [#131](https://github.com/cyrox007/PubChat/pull/131), `8e5219e` | **No-downgrade [Android #58](https://github.com/cyrox007/PubChat-Android/pull/58) слит** `103ecb1`; **crypto-device foundation [#60](https://github.com/cyrox007/PubChat-Android/pull/60) слита, `4715e69`, CI Android enabled/disabled green**, генерирует Ed25519/X25519/signed/one-time prekeys, Keystore storage, explicit server register/revoke; E2EE send/decrypt **НЕТ** ([#59](https://github.com/cyrox007/PubChat-Android/issues/59)) | Native E2EE не реализован | **P0 security blocker**: X3DH-style 3DH/HKDF sessions, device-directory trust, AEAD encryption/ratchet/decrypt, attachments, physical interoperability and security review |
| **Safety Center**: жалобы, история, ограничения, апелляции | Web + Trust & Safety API | Нет полного пользовательского flow | Нет полного flow | **P0 safety blocker** |
| Сессии и устройства | Web + Identity API | Нет полноценного editor | Нет полноценного device revoke | Список и отзыв сессий, после-revoke поведение |
| Уведомления и доставочные настройки | Web Push/preferences | Центр + FCM foundation, неполные controls | Базовая активность, APNs отсутствует | Серверная конфигурация и реальные push-device тесты |
| Реальные device E2E | Browser coverage | Не подтверждена полная физическая матрица | Симулятор ≠ реальный iPhone | P0 перед 1.0 |

**Не маркировать «создание Space отсутствует» на Android.** Уже реализован полноценный API-backed Compose flow. Однако реализация в коде и CI green **не означают** физическую приёмку.

## Новый ожидаемый объём: Personal Feed & Media (план, 20.10.2026)

| Будущий сценарий | Backend/Web | Android | iOS | Условие готовности |
| --- | --- | --- | --- | --- |
| S3-compatible MediaService и Account storage quotas | **Запланировано [#135](https://github.com/cyrox007/PubChat/issues/135)**; действующий media security baseline не равен S3 | Нет нового API-клиента | Нет нового API-клиента | Atomic quota / multipart / reconcile / rights / privacy и реальный S3-compatible integration gate |
| Персональная стена, посты с текстом/фото/смешанными каруселями | **Запланировано [#136](https://github.com/cyrox007/PubChat/issues/136)** | Запланировано | Запланировано | Публикация и действия с серверно проверяемой приватностью |
| Лента подписок/друзей/«Для вас» | **Запланировано [#137](https://github.com/cyrox007/PubChat/issues/137)** | Запланировано | Запланировано | Block/privacy до ranking, cursor paging, серверные реакции |
| Граффити с рисовалкой | **Запланировано [#138](https://github.com/cyrox007/PubChat/issues/138)** | Запланировано | Запланировано | Touch/stylus/mouse, undo/redo, безопасная публикация |
| Видео и музыка/аудио | **Запланировано [#139](https://github.com/cyrox007/PubChat/issues/139)** | Запланировано | Запланировано | Processing/transcode, квоты, права, player |
| Stories/Highlights и Reels | **Запланировано [#140](https://github.com/cyrox007/PubChat/issues/140), [#141](https://github.com/cyrox007/PubChat/issues/141)** | Запланировано | Запланировано | TTL, audiences, CDN invalidation, video feed, real-device QA |

**Важно:** это согласованный план [Epic #134](https://github.com/cyrox007/PubChat/issues/134) и [ТЗ](social-content-media-platform-v1.md), **не существующие API/экраны**. Требуются подтверждённые code/CI/device acceptance [#142](https://github.com/cyrox007/PubChat/issues/142). Уже открытые P0 в разделах выше остаются ближайшими security/safety задачами.

## Новый ожидаемый контур автомодерации (PLANNED — 20.10.2026)

| Сценарий | Backend/Web | Android | iOS | Что остаётся |
| --- | --- | --- | --- | --- |
| Управляемые слова/фразы, словоформы, обходы и исключения | **План [#145](https://github.com/cyrox007/PubChat/issues/145), [#146](https://github.com/cyrox007/PubChat/issues/146)**. Существующий AI-copilot работает только после report claim | Будущие server-backed rejection/masking UI | Аналогично | Единый server matcher, admin preview, проверка всех plaintext write paths и delivery surfaces |
| Пожаловаться из конкретного сообщения + контекст | **Report API существует**, но evidence `reported_message_only`; [context #147](https://github.com/cyrox007/PubChat/issues/147) **НЕ готов** | Требуется report-button/контекстный UX | Требуется report-button/контекстный UX | Bounded case evidence, separate DM privilege, retention/audit |
| E2EE DM report | Ciphertext не доступен для server-side lexicon | Запланировано добровольное disclosure [#148](https://github.com/cyrox007/PubChat/issues/148) | То же | Никакого server E2EE backdoor; only reporter-selected evidence |
| Фото, граффити, посты, комментарии, видео/аудио, Stories, Reels | **Будущая медиаплатформа [#134](https://github.com/cyrox007/PubChat/issues/134)** + scan OCR/ASR/AI [#149](https://github.com/cyrox007/PubChat/issues/149) | Будущие report/media-review UI | Будущие report/media-review UI | S3 quarantine, rights, published content must pass review/visibility |
| AI moderation console | **Advisory AI copilot уже есть**; новая orchestration/UI [#150](https://github.com/cyrox007/PubChat/issues/150), [#151](https://github.com/cyrox007/PubChat/issues/151) запланирована | Safety Center status remains incomplete | Safety Center status remains incomplete | Shadow calibration, no punitive AI bypass, reviewer context and privacy [#152](https://github.com/cyrox007/PubChat/issues/152) |

Каноническое ТЗ [`unified-content-moderation-v2.md`](unified-content-moderation-v2.md), [Epic #144](https://github.com/cyrox007/PubChat/issues/144). **Ни один Planned пункт не становится code-complete из-за документа.** Существующий нативный E2EE/Safety Center P0 остаётся открытым.

## Приоритеты после текущих PR

1. **P0: Space invitations acceptance** — Android [#56](https://github.com/cyrox007/PubChat-Android/pull/56) **слит** в `master`, `07cae34`, обе CI-конфигурации green. Нужны реальные Android устройства, blocked/private/expired/revoked/invite-only и Web↔Android cross-client тесты. Далее — недостающий iOS flow. Не повторять Android Create Space и invitation inbox.
2. **P0 security: Messenger E2EE на Android**, затем iOS: первичный Android fail-closed/no-downgrade этап [#58](https://github.com/cyrox007/PubChat-Android/pull/58) уже слит, `103ecb1`; backend HTTP mutation enforcement **слит** в [#131](https://github.com/cyrox007/PubChat/pull/131), `8e5219e` (backend/frontend/security/browser smoke green). **Первый шаг native crypto #59 завершён в коде** — [Android PR #60](https://github.com/cyrox007/PubChat-Android/pull/60), merge `4715e69`, обе Android CI-конфигурации green: Account-scoped device keys, Ed25519/X25519 signed prekeys, encrypted Keystore private key storage, server register/list/revoke (физические Android устройства ещё НЕ проверены). **Следующий этап — [Android #61](https://github.com/cyrox007/PubChat-Android/issues/61), parent #59 остаётся открытым:** сессии 3DH/HKDF, проверка identity/prekey и directory transparency, envelope fan-out, ratchet, encrypted send/decrypt/attachments, Web↔Android физические тесты. Нельзя выдавать блокирующий E2EE-баннер за криптографию.
3. **P0 safety: нативный Safety Center** для Android/iOS — server-mediated reports/restrictions/appeals, приватные проекции, разрешения и запрет утечек.
4. **0.7 незакрыто:** DM consent **уже слит на Android/iOS** ([Android #53](https://github.com/cyrox007/PubChat-Android/pull/53), [iOS #16](https://github.com/cyrox007/PubChat-iOS/pull/16)); остаются cross-client consent/block/revocation, публичный Multi-Persona contract, реальные устройства.
5. **0.8/0.9:** полноценные Activities, offline/reconnect, notification preferences/delivery, устройства/сессии, репутация и product experience. Эти направления не закрываются одним набором экранов.

## Обязательное правило для каждого следующего PR

До начала реализации: (1) посмотреть `main/master`, открытые и слитые PR и GitHub Issues **во всех трёх репозиториях**, (2) проверить уже существующие API и экраны, (3) выбрать один пользовательский сценарий, а не список визуальных элементов.

В том же PR либо связанном docs PR **обновить эту таблицу**, соответствующую матрицу нативного репозитория и body/чекбоксы родительской задачи. При merge указать: ссылку, SHA, backend контракт, клиентский статус, CI и физический QA отдельно. Если QA отсутствует — оставить соответствующий чекбокс открытым. Следующая задача берётся из первого незавершённого сценария по приоритету, **не из устаревшего README**.

## Условия завершения сценария

- **Code complete:** API/permission + UI + loading/empty/error/retry + явное состояние отказа.
- **CI verified:** точный head с подтверждёнными unit/integration/browser/build проверками; не объединять статус разных коммитов.
- **Device verified:** реальный Android и/или iPhone с протоколом версий/сценариев, сеть/фон/permissions.
- **Parity accepted:** Web/Android/iOS одинаково ведут себя для success и 401/403/409, privacy, revoke, retry; нет обхода серверных правил. Только после этого родительская parity-задача может быть закрыта.
