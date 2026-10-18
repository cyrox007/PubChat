# Репозитории и клиенты PubChat

Этот документ фиксирует **текущее состояние GitHub**, а не планируемые переименования.

| Назначение | Репозиторий | Основная ветка |
| --- | --- | --- |
| Backend, API, Web SPA/PWA, эксплуатационные инструкции | [cyrox007/PubChat](https://github.com/cyrox007/PubChat) | `main` |
| Нативное приложение Android | [cyrox007/PubChat-Android](https://github.com/cyrox007/PubChat-Android) | `master` |
| Нативное приложение iOS | [cyrox007/PubChat-iOS](https://github.com/cyrox007/PubChat-iOS) | `main` |

**Три направления:** Web/backend, Android, iOS. **Переименование выполнено:** основной backend/web репозиторий теперь `cyrox007/PubChat`; прежний `cyrox007/chat` может перенаправляться на новый адрес. Используйте только канонические URL.

## Правила совместимости и источники истины

- Backend API, база данных и realtime contracts принадлежат `cyrox007/PubChat`. Android и iOS — независимые нативные клиенты, а не копии backend. Web, Android и iOS должны реализовать одинаковые пользовательские сценарии к 1.0.
- HTTP по умолчанию: `https://pubchat.ru/api`. Клиент использует `/identity/v2`, `/realtime/v2/tickets`, `/notifications/v1/native-push/devices`, `/calls/v1/*`; WebSocket для звонков: `/ws/v2/calls`.
- Session/device bindings, доступ/модерация, privacy и авторизация всегда проверяются на сервере; не доверяйте client UI.
- Web Push/VAPID и FCM — разные каналы. Android FCM требует отдельной настройки Firebase, server credentials, зарегистрированного токена и delivery-тестов.
- SDP/ICE не должны попадать в push. Сервер хранит короткоживущее предложение вызова в Redis (TTL 60 секунд), выдаёт его только авторизованному адресату и доставляет generic FCM wakeup. Для ICE renegotiation используют `ice_restart=true` без нового push.
- WebRTC DTLS-SRTP шифрует медиатранспорт, но **не** означает verified application E2EE или привязку к идентичности устройства.

## Текущий Android-срез (разработка, не production parity)

В клиенте присутствуют вход/регистрация, People/Persona basics, Spaces realtime/chat, Messenger text/actions, центр уведомлений, deep links, FCM registration, нативный WebRTC audio/video, foreground service и отдельные действия входящего вызова. Реализованы короткоживущий recovery offer и ограниченные попытки восстановления signaling/ICE.

**Нельзя считать завершённым:** Android E2EE-DM, полный паритет Spaces/Persona/Safety/Admin, DM-вложения, verified call E2EE, Telecom/гарнитуры/устройства, Wi-Fi↔LTE handover, real-device end-to-end проверки. Подробности и актуальный чек-лист находятся в [Android README](https://github.com/cyrox007/PubChat-Android/blob/master/README.md).

## Процедура изменения имени основного репозитория

После фактического переименования `cyrox007/PubChat` → `cyrox007/PubChat`:

1. Проверено по GitHub: серверный репозиторий имеет идентификатор `950435997` и каноническое имя `cyrox007/PubChat`.
2. Сменить remote в существующих клонах backend: `git remote set-url origin https://github.com/cyrox007/PubChat.git`.
3. Обновить ссылки в README, документации обоих проектов, scripts/CI badge, инструкции деплоя и внешние интеграции (webhooks, GitHub Apps, tokens, permissions).
4. Проверить GitHub Actions, workflows с явным `repository`, checkout, branch protection/environment secrets и деплой, не раскрывая секреты.
5. Проверить реальные CI/deploy на новом адресе; GitHub redirects полезны, но не заменяют актуальных URL в документации.

## Матрица верификации Android ↔ Web

| Сценарий | Требуемая проверка |
| --- | --- |
| Auth/device identity | login, refresh, logout, revoke, смена устройства |
| Messenger | live DM, read/unread, moderation, fail-closed E2EE policy |
| Spaces | join, history, attachment 2 MiB, reconnect |
| Push | foreground/background, блокировка экрана, token rotate, TTL call offer |
| Calls | Android ↔ Android/Web, mic/camera, DTLS-SRTP, relay TURN, ICE restart, glare |
| Network recovery | Wi-Fi ↔ LTE, краткий обрыв, долгий обрыв, потеря signaling |
| Android runtime | permissions, FGS, power saver, notifications, speaker/headset/Bluetooth |
| Launch | verified HTTPS app links, crash/ANR, privacy/security review |

До прохождения матрицы CI build следует трактовать как **проверку компиляции и тестов**, не как свидетельство production-готовности клиента.

## iOS — новое нативное направление

Репозиторий `cyrox007/PubChat-iOS` создан и первоначально был пустым.
Первый этап реализуется в [iOS PR #1](https://github.com/cyrox007/PubChat-iOS/pull/1):
SwiftUI + XcodeGen + GitHub Actions macOS без локального Mac, Identity v2
и Keychain, стартовые read-only каталоги. Пока CI и iPhone device tests не пройдены,
эта реализация не считается готовой.

- Xcode/simulator compilation: GitHub Actions на стандартном `macos-26` без Apple signing.
- Signed `.ipa` и TestFlight требуют Apple Developer, сертификатов и App Store Connect;
  секреты — только в GitHub Secrets/Environments.
- Уведомления iOS должны использовать APNs. Web Push и Android FCM не являются APNs.
- WebRTC, E2EE, deep links, permissions, background modes и восстановление звонков
  требуют отдельной нативной реализации, security review и испытаний на iPhone.

## Функциональный паритет трёх клиентов: обязательное условие PubChat 1.0

Любой общий эпик имеет одну backend/API спецификацию и три реализации:
**Web/PWA + Android + iOS**. Отдельный клиент может временно отставать, но
эпик нельзя закрывать и выпускать как часть 1.0 до одинаковых сценариев,
обязательных ошибок/ограничений доступа, совместимых realtime-протоколов и
подтверждающих тестов на трёх платформах.

Обязательные проверки: Identity/Persona, согласие на контакты, Social
Graph, Spaces/Activities, Messenger и E2EE, звонки и фоновые переходы,
уведомления, репутация/достижения, Safety/апелляции, подписки/подарки,
доступность и восстановление после потери сети.

Целевые milestones: 0.7 Social Core, 0.8 Living Spaces,
0.9 Product Experience, затем 1.0 parity/release gate.
Матрица исходного iOS-среза ведётся в
[PubChat-iOS/docs/PARITY_MATRIX.md](https://github.com/cyrox007/PubChat-iOS/blob/feat/ios-foundation-ci/docs/PARITY_MATRIX.md).
