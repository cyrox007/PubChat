# Moderation Lexicon v1 — версии словарей и безопасный предпросмотр

> **Фактический этап #145**: администратор получает CRUD *снимков полного словаря* (путём создания новой неизменяемой ревизии), выбор/откат, shadow/off, интерактивный предпросмотр, аудит. **Проверка при реальной отправке/редактировании/публикации НЕ подключена** — это следующая задача [#146](https://github.com/cyrox007/PubChat/issues/146), потому что необходимо закрыть ВСЕ HTTP/WS send paths до включения цензуры. Этот этап не является AI/LLM и не читает E2EE.

## Администратор

Раздел `Trust & Safety → Словари и цензура` появляется только при permission `moderation.policy.manage` (через действующий RBAC; выдаётся роли admin, не Space moderator и не обычному platform moderator).

В редакторе также есть **импорт и экспорт JSON**, сравнение с активной ревизией (добавленные/изменённые/удалённые правила) и выбор поверхности при тестировании текста.

В редакторе:
1. Добавьте правило: основной термин, язык `ru/en`, категория, строгость `low/medium/high`, области `all/space_chat/messenger_plaintext/profile/activity/post/comment/story/reel/media_caption` (без E2EE ciphertext), `token` точное слово / `phrase` фраза / `stem` явно заданная основа с ограниченным набором окончаний, предполагаемое действие `warn/mask/reject/hold`, дополнительные варианты и исключения; активность.
2. Введите пример в тестовую форму и нажмите «Проверить текст». Отобразятся найденные spans/категории/предлагаемые действия и **preview**, но реальный чат останется без фильтра. Тестовый текст не сохраняется в БД или журнале.
3. Укажите причину и «Сохранить новую ревизию». Изменение списка **не редактирует** прошлую ревизию.
4. «Опубликовать в shadow» помечает активную ревизию, **без автоматического вмешательства в чаты**. «Выключить» отключает режим, сохраняя ревизию. Откат осуществляется выбором предыдущего snapshot и его повторной публикацией в shadow с причиной. В журнале доступны предыдущая/новая ревизии, режим, автор и время.

Никаких встроенных непрозрачных списков «запрещённых слов» не поставляется: владелец политики задаёт точный approved список, калибрует исключения и обоснованную строгость. Морфология в первой версии **ограничена** типовыми окончаниями, не является полным лингвистическим парсером: администратор явно задаёт stem и исключения. Модельный AI, поведенческие сигналы и санкции не меняются.

## Контракт

Новые маршруты под `/trust-safety/v1/lexicon`:
- `GET /` — активная ревизия/режим/правила и последние 25 ревизий;
- `GET /revisions/{revision}` — полный immutable snapshot;
- `POST /revisions` — full replacement snapshot, только создание, до 200 правил, обязательная причина, сериализация через singleton row lock PostgreSQL;
- `POST /activate` — rollback/publish через revision + `off|shadow` + причина, запрещён `enforce`, нельзя активировать пустую ревизию в shadow;
- `POST /simulate` — текст до 4000 символов, по сохранённой ревизии либо временным валидированным правилам, ответ `revision/mode/matches/preview/would_block/enforced=false`;
- `GET /audit` — bounded audit (max 100).

Все эти API **требуют** `moderation.policy.manage` даже для чтения/симуляции, потому что словарь может быть внутренним security-policy артефактом. Все requests версионированы, Pydantic `extra=forbid`, bounded; arbitrary regex запрещены (ReDoS). Для смешанных алфавитов — NFKC/casefold, нормализация `ё`, Latin homoglyph inside Cyrillic words, минимальная латинская/русская цифрозамена, детекция отдельных букв, разделённых короткой пунктуацией (НЕ whitespace). Позиции в результате соответствуют исходным символам; маскируются только подходящие фрагменты.

### Модель хранения

- `moderation_lexicon_state` — singleton id=1 с `active_revision`, `mode=off|shadow` и автором;
- `moderation_lexicon_revisions` — immutable snapshots JSON с автором/причиной/временем;
- `moderation_lexicon_audit` — журнал создания/активации/отключения без текста симуляции и истории сообщений;
- миграция `y3n9r7m22002` следует за `x2m8q6l11001`, initial state off, **admin-only permission** `moderation.policy.manage`.

В текущих таблицах **нет** пользовательских сообщений, raw prompts, списков получателей или личной E2EE-переписки. Режим `shadow` пока означает выбор ревизии для её явной проверки в редакторе, а не автоматическую фоновую проверку всех пользовательских send/edit; это будет следующий integration PR.

## Тесты и следующие этапы

- Unicode+homoglyph+split punctuation, stem inflections, phrase/variants, false-positive exceptions, exact word boundaries, allowed actions, data bounds, RBAC routes and rollback readiness.
- Следующий [#146](https://github.com/cyrox007/PubChat/issues/146) обязательно охватит create/edit/reply/forward через Messenger plaintext и Space HTTP/WS, предрендер push/search/quotes, profile/posts/media captions. Сначала shadow sampling с отсутствием личных исходных текстов в логах, затем calibrated enforcement после отдельного operational approval. Никакая серверная цензура **не может** проверять end-to-end encrypted DM ciphertext; для них есть добровольные client-local предупреждения и report evidence [#148](https://github.com/cyrox007/PubChat/issues/148).
