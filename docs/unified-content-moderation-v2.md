# Unified Content Moderation v2 — цензура, контекст жалоб и AI-анализ

> **Статус: SPECIFICATION / PLANNED, 20.10.2026.** Этот документ расширяет существующую модерацию PubChat, а **не объявляет реализованными** новые фильтры, OCR/ASR, всеповерхностную автомодерацию или контекстный просмотр DM.
> Epic: [#144](https://github.com/cyrox007/PubChat/issues/144). Базовый действующий домен: [Trust & Safety v1](trust-safety-v1.md), [moderation privacy](moderation-privacy-v1.md), [reported-media retention](moderation-media-retention-v1.md), [E2EE Messenger](messenger-e2ee-v1.md), [social content roadmap](social-content-media-platform-v1.md).

## 1. Зачем и что уже есть

Продуктовая цель: пользователь PubChat должен иметь возможность **сообщить о нарушении непосредственно из любого сообщения или контента**, а платформа — автоматически распознавать заранее запрещённые выражения и фразы в доступном ей открытом тексте **до публикации/доставки**. При расследовании модератор видит конкретный объект и **ровно тот окружающий контекст, на который имеет право**. Для публикуемых медиа действуют предварительные проверки, карантин и разбор жалоб. Языковая политика настраивается через понятную панель.

**Фактически реализовано на момент ТЗ**:
- `POST /trust-safety/v1/reports` с `source_type=persona|messenger_message|space_message`; для `messenger_message` авторитетная связь с reporter как получателем, для `space_message` membership check; `source_uid` выбирается при создании жалобы.
- Human-claimed platform queue и `GET /trust-safety/v1/reports/{uid}/evidence`: выбранное сообщение и его медиа (при наличии), но **`context_policy=reported_message_only`**, соседние сообщения не возвращаются.
- Привилегированный AI **copilot** только для уже закреплённой жалобы: provider-neutral JSON schema, минимальный payload и рекомендации, которые человек принимает/отклоняет. AI не имеет права выдавать санкцию самостоятельно.
- Meta-behavior signals (anti-spam/invite pressure), reversible quarantine/remove для пожалованных **локальных** uploads, audit/appeal/privacy projections, ограниченные **default-off** protective holds после human-reviewed shadow calibration.

**Не реализовано новым ТЗ:** расширяемые управляемые словари, единая серверная preflight-проверка всех публикаций, модерация будущей стены/Reels/Stories, bounded context snapshots с DM privacy, согласованная с пользователем E2EE evidence, полноценный пользовательский report UX на всех клиентах, model-driven multimodal scanning. Не переписывать имеющиеся workflow и права ради появления второй системы.

## 2. Матрица покрытия: что система должна уметь

| Surface | Прямая жалоба | Проверка перед показом / записью | Evidence и граница доступа |
| --- | --- | --- | --- |
| Space chat (текст, цитата, редактура, media, reply) | Из меню любого сообщения | Server lexicon + surface policy до хранения/fan-out, media scan до public delivery | Пожалованное сообщение, максимум ограниченные соседние в **том же** Space с membership/case authorization |
| Личные DM без E2EE | Из bubble сообщения | Lexicon gate до server plaintext send/edit/reply, anti-spam, запрет известных фраз в notification snippets | Сообщение + **минимальный** контекст по claimed case и отдельной привилегии private evidence view; без полного доступа к DM history |
| E2EE DM (ciphertext) | Из bubble локально расшифрованного сообщения | **Невозможна обязательная серверная проверка plaintext**; opt-in клиентский фильтр/предупреждение только локально; блокировка/metadata abuse | **Только явно выбранное и раскрытое заявителем** локально расшифрованное сообщение и согласованные соседние, без backdoor/запроса ключей |
| Persona/profile/имя/bio, Space titles/rules/Activities | Report на профиль/объект | Единый deterministic preflight на create/edit | Версия выбранного поля, точное место и соответствующая область доступа |
| Личная стена, пост, комментарий, репост/цитата, hashtags | Из поста/комментария | Preflight текста и ссылок + проверка вложений; при edit повторный scan | Автор/Persona, версия текста, медиа и опубликованная аудитория |
| Фото, галереи, изображения, **граффити** | Из медиа / поста | MIME/content/AV + OCR текста и image AI; graffiti raster preview и безопасная модель исходника | Пожалованная asset-version, preview, scan/classification reason, retention policy |
| Видео, Reels, Stories | Из видео/фрагмента/Story | Media quarantine → sampled frame OCR/vision, captions/transcript ASR, title/comments/text overlay moderation; transcode до ready | Reported version, bounded relevant frame/timecode; просроченный Story report хранит разрешённые case evidence, не становится публичным |
| Музыка, аудио/voice | Из публикации/плеера | Аудиотранскрипция (если допускается) + toxic speech detection, метаданные/обложка, rights declaration/takedown | Фрагмент/таймкод/транскрипт по consent/privacy, не постоянный публичный транскрипт private E2EE |
| Файлы/ссылки/приглашения/соцдействия | По доступному объекту | Rate/anti-spam/scam URL safety/impersonation, account-level restriction | Привязанный объект, поведенческие агрегаты; отсутствие неограниченного user-activity surveillance |

Социальные медиа [#134](https://github.com/cyrox007/PubChat/issues/134) ещё **планируются**: их модерация внедряется в тех же функциональных PR до включения publishing, а не отдельно «когда появятся жалобы». Все действия должны использовать один Trust & Safety API/domain и системный Account-level block/restriction; Space-local permissions не превращаются в platform moderation.

## 3. Регулируемая текстовая цензура: простое управление, непростой matcher

### 3.1 Виды правил

Политика versioned, хранится в PostgreSQL (не конфиг из фронтенда). Состав:
- platform rules: минимальная обязательная политика, авторизованно редактируемая;
- optional Space rules: дополнительные слова и локальная мягкая политика под властью Space owner/moderator, но **не право отключать platform floor**;
- user preferences (позднее): дополнительное скрытие грубой лексики **для самого пользователя**, без изменения глобальной moderation evidence;
- languages/locale and surfaces, category, severity, match kind, target action, allowlist exceptions, active window, status, revision, actor/reason.

**Matching modes**: exact token, exact phrase, morphological/lemma forms for ru/en, boundaries/stems with safe dictionary exclusions, limited literal regex patterns only after validation. Homoglyph, mixed Cyrillic/Latin, zero-width characters, letter repetition, punctuation splitting, digit substitution, transliteration and common obfuscation normalization. Должны быть защитные лимиты на fuzzy edit distance, CPU, размер текста и длину шаблона; опасные нерегламентированные regex запрещены, чтобы фильтр сам не стал DoS.

**Политика не должна быть чрезмерной:** отдельные настройки «показать предупреждение», «замаскировать», «отклонить», «на проверку», контекстные исключения для общеупотребительных слов, цитат, имен и научных выражений. Ложные совпадения видны в shadow отчётах и их можно исправить без деплоя. Совпадение с грубым словом **не означает автоматически** harassment/hate/crime; не выдавать тяжёлые санкции на основании лексического триггера.

### 3.2 Action pipeline и UX

Поток обычного plaintext: authenticated write → target/surface/privacy/authority check → **content preflight** (deterministic ruleset revision) → `allow | warn | mask | reject | hold_for_review` → durable entity + audit decision → realtime/notification/search/feed projections. Если пользовательское поле редактируется или цитируется, проверять снова. Никакой client-only censor или post-send flash «слово было плохим», если уже показали оригинал другим.

- `mask`: видимый текст с безопасными заменами, без оригинальных запрещённых фрагментов в push, quoted preview, search snippets, WebSocket fan-out и UI cache; original допускается лишь в ограниченном evidence store, если policy retention/review требует, и никогда не пишется в логи.
- `reject`: без публикации, понятное объяснение категории и возможность исправить сообщение (не раскрывать сами секретные шаблоны в attacker-friendly деталях).
- `hold`: публичный контент не доступен до решения; sender видит «На проверке». Quarantine не даёт CDN/Media URL публичного доступа. Для DM текстового hot path не запускать тяжёлую синхронную LLM.
- `warn`: автор исправляет текст до отправки или явно подтверждает допустимый мягкий случай только если platform policy позволяет. Никакого подтверждения, обходящего запрещённые категории.

Дизайн response/trace: `policy_revision`, `action`, `rule_category`, `surface`, internal match spans only privileged, `decision_uid`, `review_case_uid` при необходимости; exact API fields принимаются отдельным contract PR. Не делать несовместимые правила в Web, Kotlin, Swift.

### 3.3 Панель «Словари и правила»

Админ может добавлять/редактировать запрещённые слова/фразы, их варианты/шаблоны, категорию/строгость, применять по surface и языку, включать/выключать, добавлять исключения. Поиск и фильтры, импорт/экспорт с проверкой, версии и откат, **живой предпросмотр**: ввёл пример текста → видно какие слова найдены/какой policy revision сработал/как будет выглядеть итог → сколько потенциальных ложных срабатываний в сухом прогоне.

Запрещённые списки и операции управления доступны только с отдельным permission `moderation.policy.manage`. Значительные изменения требуют подтверждения и audit trail. Начальный релиз — shadow/dry-run, потом staged enforcement после FP evaluation. Не публиковать полный внутренний словарь анонимным клиентам.

## 4. Жалоба именно из сообщения с понятным контекстом

### 4.1 Пользовательская операция

В контекстном меню **каждого** сообщения/поста/Story/Reel/медиа есть `Пожаловаться` → повод + необязательное описание → безопасный предпросмотр выбранного объекта → submit. Source UID сервер определяет как существующий и разрешённый reporter (как сейчас). Кнопка «Заблокировать», «Скрыть», «Пожаловаться» не смешивается с мгновенной санкцией. Результат — подтверждённая жалоба, отдельная история статусов, право на обращение. Loading/duplicate/403/404/429/offline-retry на Web/Android/iOS через тот же контракт.

### 4.2 Evidence snapshot и соседние сообщения

Текущий backend сохраняет источник и показывает `reported_message_only`. v2 добавляет **immutable purpose-limited case evidence**: точный reported message с временем, author reference, версией/attachments, source hash. Последующие edit/delete не отменяют уже законно созданное evidence; expiry/appeals определяют retention, а не уничтожение наугад.

- В **Space**: ограниченный контекст той же комнаты/ответной ветки, например policy default `3 before + 3 after` в bounded time window. Это проектная начальная величина, **не реализованный параметр**. Несвязанные приватные Rooms и другие Persona не попадают в просмотр. Модератор Space видит только разрешённый им контент; platform moderator — claimed platform case.
- В **plaintext DM**: message-only по умолчанию; запрос соседнего контекста только после claim, отдельного `moderation.evidence.private_view`, записи причины и audit. Ограниченный временной/количественный фрагмент между **теми же двумя участниками**. Никакого общего «все сообщения пользователя», выгрузки переписки или доступа к незаявленным беседам.
- Нужен больший фрагмент — **запрос расширения evidence** с justification и повышенным review, а не кнопка «загрузить ещё 1000 сообщений». Нельзя использовать moderation UI как интерфейс слежки.
- E2EE: клиент показывает список **конкретно выбранных** расшифрованных сообщений, раскрывает кто увидит и зачем; пользователь явно подтверждает отправку. Сервер получает лишь этот disclosure bundle, а не универсальные ключи. Происхождение/целостность envelope связывается с reported UID и ciphertext metadata, но даже такая связь **не доказывает достоверность клиентского plaintext от недобросовестного заявителя**; требуются доказательственные ограничения/дополнительная проверка. Скрытый «мастер-ключ» запрещён.

В модераторском case view: reported message выделено в временной ленте, показываются ограниченный разрешённый контекст, вложение/таймкод, статус `reported only` / `approved plaintext context` / `user-disclosed E2EE evidence`, и явная причина отсутствия контекста. Каждое чтение sensitive evidence/изменение дела аудируется.

## 5. AI-оркес­трация / методы автоматической модерации

Два **разных** направления:

1. Быстрый, воспроизводимый **deterministic policy engine** для forbidden words/phrases, word forms, safe matches, ссылки/spam controls. Результат может быть `mask/reject` до публикации, если policy проверена и enforcement включён.
2. Provider-neutral AI **advisory/triage** для сложных случаев (контекстная агрессия/травля, спам, unsafe image/video, OCR, speech-to-text, угрозы, мошенничество). Тяжёлые санкции только human moderator через существующий hierarchy/permission API. Автоматический hold public media возможен по утверждённой, проверяемой политике; не расширять автоматически права существующего calibrated protective holds.

AI model version, category, confidence, reproducible summary, trace reference (без сырого prompt и chain-of-thought), reviewer label `correct/false_positive/unclear`, privacy-safe metrics, provider cost/rate limit, per-surface error fallback, model rollout/shadow calibration, rollback. Для внешнего provider нельзя автоматически отправлять DM history, E2EE plaintext, приватные медиа или идентификаторы пользователей без соответствующего основания/согласия и data processing policy.

Media pipeline: upload quarantine → validate/scan → OCR frames/images/graffiti → ASR captions/audio → permitted AI assessments → `ready|review|rejected` → published public media with permissioned CDN/S3 delivery. Вложенный в пост контент может быть в версии/preview, но **не публично доступен**, пока нужная проверка не пройдена. Не заявлять, что OCR/ASR/LLM гарантированно находят все нарушения.

## 6. Интерфейс модератора

Не заменять существующий `TrustSafetyQueueView.vue`: расширить одной удобной рабочей поверхностью:

- **Очередь требует внимания** по умолчанию: новые, взятые в работу, эскалации, quarantine/AI candidates. Прочитанные/закрытые/архив отдельно.
- Карточка `жалоба — source — категория — приоритет — время — claim`, компактное различение текста/DM/E2EE/видео/фото.
- Справа (или отдельным экраном на телефоне) case viewer: **выделенное сообщение + разрешённый контекст**, media preview с безопасным proxy, OCR/ASR фрагменты, audit и решения.
- AI suggestion показывать рядом с ручным разбором, почему рекомендовано и модель/ревизию, не превращая в кнопку автоматической блокировки без server RBAC.
- Управление словарями, симулятор правил, версия/публикация/откат в отдельной вкладке с правами.
- Claim/release, назначение, карантин/restore/remove, justified resolution, temporary restriction, escalation, appeal, reverse action с аудиторским следом; отсутствие полномочий не маскируется frontend.
- AJAX/API data fetching, bounded paginated list, skeleton/retry/empty/selection-preserving navigation, доступность/клавиатура, отзывчивость. **Не** загружать тысячи сообщений, приватные превью или сырой E2EE контент при открытии главной страницы.

## 7. API/data/permissions (предложение, ещё НЕ реализовано)

Домен в существующем `components/moderation` + versioned endpoints, reuse `/trust-safety/v1`, `/moderation/v1`.

Предлагаемые сущности/концепты: `ModerationPolicyRevision`, `ModerationDictionaryEntry`, `ModerationDecision`, `ModerationSubject`, `ModerationEvidenceSnapshot`, `ModerationEvidenceContextGrant`, `ModerationMediaScan`, `ModerationClassifierRun`. Окончательная schema закрепляется в implementation ADR; сохранять PostgreSQL source-of-truth, transactional referential integrity, bounded background workers, purpose-scoped encrypted evidence storage and retention+backups policy. AI token budget and per-source rate guard. Возможные endpoints: `/trust-safety/v1/policies` (RBAC), `/trust-safety/v1/policies/simulate` (privileged), existing `/reports` plus limited-context endpoint, `/media/v1/{asset_uid}/moderation` (service-only) — **проектные, не существующие маршруты**.

Разделение прав:
- platform moderator existing `moderation.platform.manage`, `moderation.platform.restrict` и текущие authority hierarchy;
- **новое** право `moderation.policy.manage` для правил; `moderation.evidence.private_view` для plaintext DM context; `moderation.media.review` для будущего S3 review может быть отделено от уже существующего `moderation.platform.media.manage`, но **не заменяет/не расширяет** его без migration.
- Space moderator видит/настраивает только разрешённую Space область и не получает права читать личку или отменять platform rules;
- privileged decision/action audit, immutable moderation events, reporter privacy projection, appeal/revoke + retention.

### Реализационный срез #145 — словарь/симулятор

Функциональный PR #145 создаёт управляемые admin словари с immutable revisions, role permission, предпросмотром, историей и shadow/off без enforcement. Полный текст/архитектура [`moderation-lexicon-v1.md`](moderation-lexicon-v1.md). **Реальный preflight и автоматическая цензура пользовательских сообщений ещё не реализованы** до #146. Поставщик AI-copilot не получает эти полномочия.

## 8. Этапы и обязательная приёмка

1. **P0/P1 foundation**: правила/лексикон/симулятор [#145](https://github.com/cyrox007/PubChat/issues/145) → deterministic synchronous preflight для plaintext [#146](https://github.com/cyrox007/PubChat/issues/146), с tests на все входы; не ломать chat realtime.
2. **Evidence and reports**: report button + immutable bounded Space/plaintext DM contexts [#147](https://github.com/cyrox007/PubChat/issues/147), E2EE consent disclosure [#148](https://github.com/cyrox007/PubChat/issues/148). Это часть существующего незакрытого Safety Center, не повод закрыть его заранее.
3. **Content/media**: media/MultiModal moderation [#149](https://github.com/cyrox007/PubChat/issues/149) интегрируется с [social content #134](https://github.com/cyrox007/PubChat/issues/134) и [S3 #135](https://github.com/cyrox007/PubChat/issues/135) **до** публичного выпуска постов, историй и Reels.
4. **AI orchestration** [#150](https://github.com/cyrox007/PubChat/issues/150) и user-friendly moderator console [#151](https://github.com/cyrox007/PubChat/issues/151) поверх уже работающего copilot; QA and privacy rollouts [#152](https://github.com/cyrox007/PubChat/issues/152).

**DoD:** CI exact head; PostgreSQL/Redis/S3 fixture + browser and native contract cases; Unicode obfuscation, false-positive, wordform coverage, server edit/quote fan-out, E2EE ciphertext must not be logged/inspected, bounded context authorization and claim, cross-RBAC, no AI punitive bypass, provider down/queue/retention; physical Android/iPhone and report action UX. Раздельно помечать code / CI / real device / production rollout. ТЗ ≠ функциональная готовность.

## 9. GitHub work breakdown

[Parent Epic #144](https://github.com/cyrox007/PubChat/issues/144):
[#145 dictionary/rules](https://github.com/cyrox007/PubChat/issues/145),
[#146 server preflight](https://github.com/cyrox007/PubChat/issues/146),
[#147 reports and context](https://github.com/cyrox007/PubChat/issues/147),
[#148 voluntary E2EE evidence](https://github.com/cyrox007/PubChat/issues/148),
[#149 multimodal](https://github.com/cyrox007/PubChat/issues/149),
[#150 AI orchestration](https://github.com/cyrox007/PubChat/issues/150),
[#151 UX/admin](https://github.com/cyrox007/PubChat/issues/151),
[#152 acceptance](https://github.com/cyrox007/PubChat/issues/152).

В каждом implementation PR фиксировать имеющиеся routes/components, scope, миграции, версию правил, safety gate, CI/device/production и обновлять [delivery status](cross-client-delivery-status.md). Не начинать старую задачу повторно по памяти, всегда сверять репозиторий.
