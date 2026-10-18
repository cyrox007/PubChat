# Репозитории и клиенты PubChat

Этот документ фиксирует **текущее состояние GitHub**, а не планируемые переименования.

| Назначение | Репозиторий | Основная ветка |
| --- | --- | --- |
| Backend, API, Web SPA/PWA, эксплуатационные инструкции | [cyrox007/chat](https://github.com/cyrox007/chat) | `main` |
| Нативное приложение Android | [cyrox007/PubChat-Android](https://github.com/cyrox007/PubChat-Android) | `master` |
| Нативное приложение iOS | Не создано | — |

**Переименование основного репозитория** в `cyrox007/PubChat` обсуждается, но пока **не выполнено**. В данный момент адрес `cyrox007/PubChat` перенаправляется на Android-репозиторий после его переименования. До фактического изменения не используйте его как ссылку на backend/web, иначе команды клонирования попадут не туда.

## Правила совместимости и источники истины

- Backend API, база данных и realtime contracts принадлежат `chat`. Android — независимый клиент, не копия backend.
- HTTP по умолчанию: `https://pubchat.ru/api`. Клиент использует `/identity/v2`, `/realtime/v2/tickets`, `/notifications/v1/native-push/devices`, `/calls/v1/*`; WebSocket для звонков: `/ws/v2/calls`.
- Session/device bindings, доступ/модерация, privacy и авторизация всегда проверяются на сервере; не доверяйте client UI.
- Web Push/VAPID и FCM — разные каналы. Android FCM требует отдельной настройки Firebase, server credentials, зарегистрированного токена и delivery-тестов.
- SDP/ICE не должны попадать в push. Сервер хранит короткоживущее предложение вызова в Redis (TTL 60 секунд), выдаёт его только авторизованному адресату и доставляет generic FCM wakeup. Для ICE renegotiation используют `ice_restart=true` без нового push.
- WebRTC DTLS-SRTP шифрует медиатранспорт, но **не** означает verified application E2EE или привязку к идентичности устройства.

## Текущий Android-срез (разработка, не production parity)

В клиенте присутствуют вход/регистрация, People/Persona basics, Spaces realtime/chat, Messenger text/actions, центр уведомлений, deep links, FCM registration, нативный WebRTC audio/video, foreground service и отдельные действия входящего вызова. Реализованы короткоживущий recovery offer и ограниченные попытки восстановления signaling/ICE.

**Нельзя считать завершённым:** Android E2EE-DM, полный паритет Spaces/Persona/Safety/Admin, DM-вложения, verified call E2EE, Telecom/гарнитуры/устройства, Wi-Fi↔LTE handover, real-device end-to-end проверки. Подробности и актуальный чек-лист находятся в [Android README](https://github.com/cyrox007/PubChat-Android/blob/master/README.md).

## Процедура изменения имени основного репозитория

После фактического переименования `cyrox007/chat` → `cyrox007/PubChat`:

1. Проверить через GitHub, что **именно серверный репозиторий** имеет новое имя и прежний идентификатор; не полагаться на redirect по старому адресу `PubChat`.
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
