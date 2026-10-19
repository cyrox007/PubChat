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
| Согласие на новые DM: четыре политики | `/identity/v2/privacy`, enforcement | [PR #53](https://github.com/cyrox007/PubChat-Android/pull/53): код в PR, **не merged на срез** | [PR #16](https://github.com/cyrox007/PubChat-iOS/pull/16) слит, simulator CI green | Android CI/merge, device QA обоих клиентов, повторное создание DM после revoke/block |
| Каталог Spaces, membership, room/realtime | Код | Код | Каталог; участие/realtime не завершены | Native cross-client round-trip |
| **Создать Space** (тип, доступ, категории, join policy, лимит, теги) | Реальный API `POST /spaces/v1` | **Слито [PR #51](https://github.com/cyrox007/PubChat-Android/pull/51), `05653df`** | UI/API отсутствует | На Android нужен physical QA; следующий перенос этого сценария на iOS |
| Space invitations: увидеть, принять/отклонить, войти | Web + API | Нет завершённого inbox flow | Нет завершённого flow | **Следующий Android функциональный срез**; privacy/expired/revoked invites |
| Activities / события, повторы, напоминания | Web/API | Частичная панель событий | Нет полного flow | Нативные повторения, участие, уведомления, DST |
| Messenger: чат, отправка, реакции и медиа | Web/API | Базовые действия в коде | Неполный messenger | Нативная безопасность, retry/network и privacy |
| **E2EE DM** | Web security policy/features | **Нет полноценного native verified E2EE** | Нет E2EE | **P0 security blocker**: device keys, trust, no plaintext fallback, сквозные тесты |
| **Safety Center**: жалобы, история, ограничения, апелляции | Web + Trust & Safety API | Нет полного пользовательского flow | Нет полного flow | **P0 safety blocker** |
| Сессии и устройства | Web + Identity API | Нет полноценного editor | Нет полноценного device revoke | Список и отзыв сессий, после-revoke поведение |
| Уведомления и доставочные настройки | Web Push/preferences | Центр + FCM foundation, неполные controls | Базовая активность, APNs отсутствует | Серверная конфигурация и реальные push-device тесты |
| Реальные device E2E | Browser coverage | Не подтверждена полная физическая матрица | Симулятор ≠ реальный iPhone | P0 перед 1.0 |

**Не маркировать «создание Space отсутствует» на Android.** Уже реализован полноценный API-backed Compose flow. Однако реализация в коде и CI green **не означают** физическую приёмку.

## Приоритеты после текущих PR

1. **P0: приглашения в Spaces на Android** — полноценный inbox, получение, принять/отклонить, открыть Space только после подтверждения сервера; blocked/private/expired/invite-only случаи; тесты и device QA. Это следующий *функциональный* срез, а не повтор создания Space.
2. **P0 security: Messenger E2EE на Android**, затем iOS: проверить поведение сервера при required E2EE, нативные device keys/verification/revocation, гарантированный fail-closed send и отсутствие downgrade до plaintext. Нельзя выдавать базовую отправку DM за защищённый Messenger.
3. **P0 safety: нативный Safety Center** для Android/iOS — server-mediated reports/restrictions/appeals, приватные проекции, разрешения и запрет утечек.
4. **0.7 незакрыто:** DM consent на Android [#53](https://github.com/cyrox007/PubChat-Android/pull/53) до CI/merge, cross-client consent/block/revocation, публичный Multi-Persona contract, реальные устройства.
5. **0.8/0.9:** полноценные Activities, offline/reconnect, notification preferences/delivery, устройства/сессии, репутация и product experience. Эти направления не закрываются одним набором экранов.

## Обязательное правило для каждого следующего PR

До начала реализации: (1) посмотреть `main/master`, открытые и слитые PR и GitHub Issues **во всех трёх репозиториях**, (2) проверить уже существующие API и экраны, (3) выбрать один пользовательский сценарий, а не список визуальных элементов.

В том же PR либо связанном docs PR **обновить эту таблицу**, соответствующую матрицу нативного репозитория и body/чекбоксы родительской задачи. При merge указать: ссылку, SHA, backend контракт, клиентский статус, CI и физический QA отдельно. Если QA отсутствует — оставить соответствующий чекбокс открытым. Следующая задача берётся из первого незавершённого сценария по приоритету, **не из устаревшего README**.

## Условия завершения сценария

- **Code complete:** API/permission + UI + loading/empty/error/retry + явное состояние отказа.
- **CI verified:** точный head с подтверждёнными unit/integration/browser/build проверками; не объединять статус разных коммитов.
- **Device verified:** реальный Android и/или iPhone с протоколом версий/сценариев, сеть/фон/permissions.
- **Parity accepted:** Web/Android/iOS одинаково ведут себя для success и 401/403/409, privacy, revoke, retry; нет обхода серверных правил. Только после этого родительская parity-задача может быть закрыта.
