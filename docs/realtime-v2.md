# PubChat Realtime v2

## Назначение

Realtime v2 — транспортный контракт PubChat для Vue SPA и будущих native Android/iOS клиентов. Он не принадлежит конкретному UI-фреймворку и не должен зависеть от browser-only механизмов.

Цели протокола:

- не передавать bearer/JWT credentials в WebSocket URL;
- поддерживать несколько backend workers;
- иметь распределённый presence;
- переживать временные разрывы сети без перезагрузки приложения;
- исключать повторное создание сообщения при retry/reconnect;
- применять privacy/moderation rules на сервере;
- давать клиенту понятные состояния подключения.

## Авторизация WebSocket

WebSocket URL не содержит access token, refresh token, session id или другой reusable credential.

Последовательность:

1. authenticated client вызывает `POST /realtime/v2/tickets`;
2. сервер проверяет Account и контекст доступа;
3. сервер выдаёт случайный короткоживущий one-time ticket;
4. в Redis хранится только SHA-256 ключ ticket с TTL;
5. клиент открывает чистый WebSocket URL;
6. первым WebSocket frame отправляется `{ "type": "auth", "ticket": "..." }`;
7. сервер атомарно consume-ит ticket;
8. сервер отвечает `realtime_ready` и только после этого соединение считается готовым.

Routes:

- Space: `/ws/v2/rooms/{room_uid}`;
- DM/presence: `/ws/v2/messenger`.

HTTP ticket request:

- `target=room` требует `room_uid` и проверяет существование/активность Space и restriction;
- `target=messenger` не принимает `room_uid`;
- ticket нельзя повторно использовать или перенести в другой target/resource.

## Redis

Redis является production requirement для Realtime v2.

Он используется для:

- one-time tickets;
- pub/sub между workers;
- distributed presence;
- distributed moderation/control events;
- rate limiting;
- client-event idempotency.

В `DEBUG=True` разрешён process-local fallback. Это только developer convenience и не является production topology.

Если Redis недоступен в production, система не должна незаметно переходить на локальную модель и создавать ложное ощущение multi-worker consistency. Ticket endpoint возвращает realtime-unavailable, а клиент показывает reconnect/degraded state.

## Presence и heartbeat

Каждый WebSocket получает server-side connection id.

Presence хранится с TTL:

- connection record;
- active connections пользователя;
- connections пользователя внутри Space.

Клиент после `realtime_ready` периодически отправляет heartbeat. Heartbeat обновляет presence TTL, но не создаёт тяжёлую запись `last_online` в PostgreSQL каждую секунду.

Online означает наличие хотя бы одного активного realtime connection Account, а не состояние одного browser tab.

## Multi-worker delivery

Python memory хранит только WebSocket objects конкретного worker.

Authoritative fan-out идёт через Redis channel. Поэтому:

- сообщение Space доходит до клиентов на всех workers;
- DM доходит до всех активных устройств Account;
- presence update распространяется между workers;
- ограничение доступа к Space может отключить пользователя независимо от worker, на котором открыт его socket.

## Reconnect и resume

SPA использует connection state machine:

`idle -> connecting -> authenticating -> connected -> reconnecting/offline`

Для Space также существует `restricted`.

Reconnect:

- не перезагружает document;
- получает новый one-time ticket;
- использует exponential backoff + jitter;
- heartbeat запускается только после `realtime_ready`;
- после восстановления Space получает небольшой recent-message window;
- DM повторно запрашивает активный conversation;
- клиент de-duplicate-ит canonical messages.

Текущий resume является safe recent-window resume, а не бесконечным event-log cursor. Полный durable event cursor можно добавить позже без изменения auth transport.

## Идентичность сообщения и подтверждения

- `frontId` — клиентский идентификатор *одной операции отправки*, создаётся до записи в БД и сохраняется неизменным при пользовательском повторе после неопределённого ACK.
- `uid` — канонический серверный идентификатор уже сохранённой записи; обновления/удаления/реакции адресуются по `uid`.
- Для новых сообщений Space и обычных DM `front_id` записывается в PostgreSQL. Уникальность ограничена `(room_uid,author_uid,front_id)` либо `(sender_uid,receiver_uid,front_id)`. Исторические записи с NULL остаются совместимыми.
- После commit ответ отправителю несёт оба идентификатора. Повтор с тем же `frontId` и в том же scope возвращает прежний канонический `uid` и **не публикуется второй раз**. При ещё не завершённой записи сервер может вернуть `duplicate_pending`, что не является подтверждением сохранения.
- В Web состояние `sent` означает «сохранено сервером», не «получено устройством». При потере ответа клиент оставляет статус `uncertain`; ручной повтор использует исходный идентификатор, без повторной генерации. Клиент объединяет временную запись с ACK по `uid` или `frontId`.
- Для E2EE криптографические неизменяемые envelopes и их собственный send ACK/retry contract остаются отдельной защищённой процедурой.
- Redis claim остаётся вспомогательным ограничителем конкурирующих операций; PostgreSQL uniqueness — окончательная гарантия для обычных сообщений. Это не полная система гарантированной доставки и не бесконечный cursor stream.

## Idempotency

Каждое новое клиентское сообщение SPA отправляет с `frontId` (UUID).

До persistence backend делает distributed idempotency claim по:

- Account;
- scope (`Space` или DM receiver);
- hash(client event id).

Повторный event с тем же ключом не создаёт вторую запись и получает `duplicate_ignored`.

Если persistence первой попытки завершился ошибкой, claim освобождается и retry снова разрешён.

Это дополняет, а не заменяет client-side de-duplication по server `uid` / `frontId`.

## Rate limits

Message rate limit применяется server-side через Redis, отдельно для:

- Space messages;
- direct messages.

При превышении клиент получает `rate_limited` + retry window и показывает спокойное inline-состояние вместо разрыва соединения.

Rate limits не являются reputation score и не покупаются.

## DM privacy

Перед persistence DM сервер проверяет:

- block в обе стороны;
- receiver `dm_policy`;
- shared Space при `shared_spaces`;
- reciprocal friendship при `mutual`;
- `nobody` / `everyone`.

Client UI не является security boundary.

Read receipt разрешён только Account, который является receiver конкретного сообщения; authorization выполняется до изменения `is_read`.

## Browser session security

После Realtime v2 Vue SPA больше не хранит access JWT в `localStorage`.

Browser model:

- access token — только in-memory JS state;
- refresh token — HttpOnly cookie;
- reload сначала показывает cached non-sensitive Persona shell, затем восстанавливает access token через refresh + `/identity/v2/me`;
- старый persisted `access_token` удаляется при hydration.

Cached Persona/UI state не является доказательством authentication или authorization.

Native Android/iOS позже используют platform secure storage, но тот же backend session/ticket contract.

## UX states

UI обязан различать:

- connecting;
- authenticating;
- connected;
- reconnecting;
- offline;
- restricted;
- privacy denied;
- rate limited.

Composer не должен обещать отправку во время reconnect/offline/restricted state. Existing content остаётся видимым, а восстановление происходит автоматически.

## Security invariants

CI блокирует:

- WebSocket routes с `{token}`;
- frontend URL patterns, похожие на token-in-path;
- запись access JWT в `localStorage`;
- regression основных ticket/idempotency contract tests.

## Следующие расширения

Realtime v2 оставляет совместимые точки роста:

- durable event cursor / stream resume;
- typing indicators;
- delivery acknowledgements beyond persisted/received/read;
- richer per-device presence;
- structured metrics/alerting around Redis and socket latency;
- push bridge для background native clients.
