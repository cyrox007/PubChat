# PubChat Social Content & Media Platform — ожидаемый функционал v1

> **Статус: PRODUCT REQUIREMENTS / PLANNED (20.10.2026).** Ничего из персональной стены, домашней ленты, граффити, Stories, Reels, S3-адаптера и новых квот этим документом **не реализовано**. Текущие безопасные загрузки Messenger/Space (`docs/upload-media-security-v1.md`) — независимый существующий baseline; они не являются социальной медиаплатформой.
>
> Родительский трек: [Epic #134](https://github.com/cyrox007/PubChat/issues/134). Реализация идёт поверх модульного backend и **единого версионированного API для Web, Android и iOS**, без дублирования правил авторизации в клиентах.

## 1. Пользовательский продукт

PubChat должен предоставлять личную стену/микроблог (в духе знакомой модели VK) для **каждого Account с отображением выбранной Persona как автора** и отдельную домашнюю персональную ленту. Это не замена Spaces, Activity, Messenger и E2EE, а отдельный социальный домен, связанный с уже существующими Account/Persona, friendships/follows/blocks, Notifications и Trust & Safety.

### 1.1 Публикации и действия

Обязательные пользовательские форматы:

| Вид | Минимальный ожидаемый сценарий |
| --- | --- |
| Текст | Публикация текста, абзацы, ссылки, emoji, упоминания/теги, черновик, редактирование, удаление |
| Картинки | Одна фотография, альбом/карусель из нескольких, подписи и alt text, оптимизированные превью |
| Текст + картинки | Один типизированный пост с текстом и упорядоченными вложениями; перестановка и удаление до публикации |
| **Граффити** | Встроенная рисовалка: кисти/цвета/ластик/толщина/undo-redo, мышь/палец/стилус, черновик, публикация рисунка как собственного типа поста с необязательной подписью |
| Видео | Видеопост, обложка, продолжительность, подготовка к проигрыванию, субтитры, адаптивное воспроизведение |
| Музыка / аудио | Оригинальные музыкальные записи и аудиопосты с плеером, названием, длительностью и правами использования; **не** незаконная копия стороннего каталога |
| Смешанный / вложения | Типизированный composition schema; дополнительные безопасные медиа, GIF/анимации, голосовые, опросы и прикреплённые ссылки как последующие расширения, не блокирующие начальный запуск |
| Истории (Stories) | Фото/видео/текстовый слой, лента историй автора/друзей, таймер 24 ч, просмотр, реакции/ответы и необязательные Highlights |
| Рилсы / клипы (Reels) | Короткие вертикальные видео, swipe feed, автор/подписка/комментарии/реакции, публикация, звук, субтитры, рекомендации |

Единые действия по разрешениям: создать/изменить/удалить/закрепить пост, лайк/реакция, комментирование, репост/поделиться (при разрешённой аудитории), сохранить, подписаться, скрыть/пожаловаться. Дополнительно в backlog: опросы, совместные посты, серия/альбом, отложенная публикация и live-stream — отдельные задачи после базовой безопасности/экономики.

### 1.2 Лента и профиль

- **Стена**: публикации выбранной Persona, закреплённые посты, сетка фото/видео, фильтры типов, просмотр автора и публикации по постоянной ссылке.
- **Главная лента**: «Подписки», «Друзья» и «Для вас»; сначала хронологический cursor feed, затем bounded органические рекомендации с настройками пользователя. «Для вас» никогда не отменяет block/privacy и не продаётся покупкой статуса.
- **Пост** имеет Account-owned записи и public author Persona snapshot/reference; Persona — **не дополнительный владелец хранилища или способ обойти блокировки/квоту**.
- Социальные действия используют **Account-level relationship/permission**; отдельные Persona могут быть приватными, поэтому сервер разрешает показ автора/контента только при соответствующей настройке видимости.
- Аудитории как минимум `public / followers / friends / only_me`, более узкие коллекции/списки — позднее. Право на просмотр заново проверяется при каждом feed/media access; пониженная приватность, block и санкции делают материал недоступным даже при старой ссылке, кэше или feed cursor.
- UI: web responsive, Android Compose, iOS SwiftUI; общий контракт и одинаковые состояния skeleton/progress/empty/offline/error/retry, no full-page reload для реакций, комментариев, листания и публикации. Медиа грузятся/открываются асинхронно.

## 2. MediaService и S3 — инфраструктурное требование, не «потом»

Новый provider-neutral `MediaStorage` contract с реализациями `LocalMediaStorage` для dev/compat и `S3MediaStorage` для production. Поддержать AWS S3 и совместимые endpoint-провайдеры (например MinIO/R2) без жёсткой привязки к одному поставщику, с configurable endpoint/region/credentials/bucket/prefix, шифрованием в хранилище, явной политикой TLS, provider health и таймаутов.

- **PostgreSQL**: владельцы, asset UID, назначения `post/story/reel/avatar/messenger/space`, MIME, размер, checksum, состояния, policy, immutable storage key, ACL, варианты, reference count, quota ledger, retention и audit. Не хранить бинарные файлы в PostgreSQL; Redis — не durable ledger.
- **Object storage**: оригинал, превью/варианты, HLS-сегменты, thumbnail, waveform. Бакет для private/quarantine отделён от публичной раздачи; никакой публичной S3 credentials/policy по умолчанию. На UI и в публикациях — server-issued asset IDs, не user-provided object paths.
- **Загрузка**: authenticate → server checks `file_type/max_upload/capacity` → reserve bytes atomically → short-lived **presigned / multipart** upload → complete with HEAD/checksum/size verification → quarantine/scan → async processing → ready/failed. Ни прямой S3 PUT от анонимного пользователя, ни доверия объявленному размеру. CORS ограничен, presigned scope привязан к конкретному object key и конечному размеру/типу, multipart части ограничены, cleanup orphan после TTL.
- **Раздача**: media authorization всегда определяет backend. Public media может отдаваться через CDN; private/friends-only — через краткоживущие signed URLs или доверенный media gateway. CDN invalidation/tombstone при block/delete/moderation, защита от угадывания URL и распространения privacy-private cached bytes; осторожно с длительными уже выданными URL.
- **Обработка**: bounded worker queue (не web worker lifecycle) для проверки сигнатур, AV/scan и quarantine, image resize/strip EXIF, видео transcode/cover/stream variants, audio normalization/preview, captions. Есть видимое processing state без «готов» до публикации.
- **Переход от `backend/uploads`**: staged dual-read/backfill/redirect без потери действующих Messenger/Space вложений и без big-bang переписывания. Нынешний `docs/upload-media-security-v1.md` является минимумом безопасности, а не разрешением всех форматов.

## 3. Персональные квоты — принцип Notes, расширенный на мультимедиа

В Notes уже применяется `StorageQuotaService` с глобальным default, per-user override, серверной сверкой размера и сериализацией операций. PubChat переносит **принцип**, но не автоматически числовые лимиты Notes: у видео, музыки и производных HLS другие расходы. Конкретные цифры — конфигурация продукта/тарифа после расчёта себестоимости, не константы в мобильном клиенте.

Владелец лимита: **Account UID** (все Persona/устройства одного Account используют одну квоту); при наличии Space-owned media возможно отдельное Space entitlement позже. Обязательные поля и правила:

- `quota_limit_bytes` — глобальная базовая квота + override для Account и/или entitlement плана, админский audit и восстановление.
- `used_bytes`, `reserved_bytes`, `remaining_bytes=max(0,limit-used-reserved)`. Учитывать originals + durable derivatives (превью, posters/HLS, аудио-версии) по заранее описанной billing policy. Временный кеш CDN/операционные внутренние резервные копии не выдавать за пользовательскую квоту; отдельно считать **фактический** provider footprint/cost.
- **Атомарная резервация** на запросе с блокировкой Account ledger в PostgreSQL + upload-idempotency key. Параллельные попытки не могут превысить `limit`. Multipart операции резервируют согласованный верхний предел; completion подтверждает фактический размер, списывает/возвращает разницу; истёкшие, отменённые, неудачные загрузки освобождают резерв ровно один раз.
- Настраиваемый `max_file_bytes` по `image/video/audio/story/reel`, допустимая длительность/разрешение, максимальное число вложений/постов в сутки, upload/processing/retry rate, bandwidth/egress и анти-abuse/спам-лимиты. При превышении — понятная клиенту ошибка с `quota/used/reserved/remaining`, без ложного «файл отправлен».
- **Удаление/общие ссылки**: один физический объект не освобождается преждевременно, пока есть разрешённые ссылки/retention holds; политика начисления первичного автора и повторных shares зафиксирована отдельно. Удаление/версия файла/restore/backups/appeal удержание должны иметь согласованный accounting lifecycle.
- Наблюдаемость: `GET /media/v1/quota` (предлагаемый API), Progress UI и экран «Использование хранилища», административные глобальные/индивидуальные лимиты и агрегаты. Обязательно reconciler storage/provider vs PostgreSQL, GDPR deletion/export, cost metrics (`stored GB / egress / media processing per MAU`).

**Предлагаемые, ещё не реализованные контрактные состояния:** `pending_upload → uploaded_unverified → quarantined/scanning → processing → ready | rejected | failed | deleted`. Нельзя пытаться показать asset публично до `ready`. Перевыпуск URLs, разблокировка квоты и удаление объектов должны быть идемпотентны.

## 4. Stories и Reels — самостоятельные домены над общими MediaService/Feed

### Stories

`Story` имеет Account/Persona author, audience, ordered slides, created/expires timestamps, per-slide media, safe captions, server-side TTL (исходное продуктовое правило **24 часа**), просмотр/seen/reaction/reply policy; отдельные `Highlights` означают осознанное длительное хранение и расход квоты. После TTL история исчезает из выдачи и публичного media ACL, даже если GC physical bytes запускается позже. Отдельно продумать viewer anonymity/списки зрителей и разрешения на ответы. Не использовать клиентское время как источник истины.

### Reels

`Reel` — короткое вертикальное видео с автором Persona, описанием, poster, duration, sound/license metadata, moderation status, public URL и feed engagement. Общий транскодер + multi-rendition streaming, limited prefetch/bandwidth, captions/accessibility/reduced motion, безопасное автопроигрывание. Swipe-клиент работает через cursor API и не делает бесконечные выборки. Рекомендации строятся только после privacy filtering. Remix/duet/использование чужой музыки допустимо только при явном rights/consent contract, не подразумевается.

## Сквозная модерация всех типов социального контента — обязательная зависимость

[Unified Content Moderation v2](unified-content-moderation-v2.md), [Epic #144](https://github.com/cyrox007/PubChat/issues/144): до публичного запуска постов, фотографий, граффити, клипов/видео/музыки, Stories и Reels сервер должен выполнять управляемую проверку подписей/комментариев/запрещённых фраз, карантин/скан/OCR/ASR/AI triage и иметь пожаловаться/разбор/appeal. [#149 мультимодальные сканы](https://github.com/cyrox007/PubChat/issues/149) и [#147 жалобы с контекстом](https://github.com/cyrox007/PubChat/issues/147) входят в матрицу приёмки [#142](https://github.com/cyrox007/PubChat/issues/142). **План, пока не реализовано.** OCR/ASR false-positives требуют human override; S3/quota publish state не должен опережать moderation gate.

## 5. Безопасность, авторские права и модерация

- Загрузка любого медиа проходит allowlist+content sniff, size check, decode limits/anti-bomb, scan/quarantine, rate-limit, строгую обработку ошибок provider/worker. SVG/active HTML, подозрительные архивы и исполняемые вложения не включаются автоматически.
- Profile privacy, block, Account restriction, mute, DM consent, аудитории и таксономия жалоб применяются к постам, Stories, Reels, комментариям, уведомлениям, reactions и медиараздаче.
- Report → human review → reversible moderation action → appeal, с явно заданным retention evidence; нет автоматической невосстановимой санкции без policy. Жалобы на авторские права, музыку и повторную загрузку требуют отдельной процедуры правообладателей.
- EXIF/GPS, геометки, персональные данные, голос/лица, цифровая безопасность несовершеннолетних (если продукт доступен им), граффити/аудио/video rights и privacy controls требуют явных default. Не логировать медиа payload, presigned credentials, приватные URLs или личное содержимое.
- Платные квоты/Plus не влияют на trust, reporting, moderation, Account block, eligibility или organic ranking. Заполненная квота блокирует загрузку нового медиа, **но не удаляет уже опубликованное без чёткой retention/grace политики**.

## 6. Предлагаемая серверная модель / API (только проект)

Не добавлять всё в существующие `Message`/`Space` таблицы. Предполагаемые сущности:
`Post`, `PostAttachment`, `PostRevision`, `PostReaction`, `PostComment`, `PostBookmark`, `FeedVisibility`, `FeedPreference`, `Story`, `StorySlide`, `StoryView`, `StoryHighlight`, `Reel`, `MediaAsset`, `MediaVariant`, `MediaUploadReservation`, `AccountStorageQuota`, `AccountStorageLedgerEntry`, `MediaProcessingJob`. Названия уточняются в ADR перед миграцией; общее правило: owner Account, public author Persona, **Post ID не равен MediaAsset ID**.

Предлагаемые versioned endpoint groups (не существующие API):

| Группа | Назначение |
| --- | --- |
| `/media/v1/*` | quota, upload session init/complete/abort, media status, URL access, admin quota |
| `/posts/v1/*` | drafts, publish, update, delete, react/comment/bookmark/repost, account Persona wall |
| `/feed/v1/*` | following/friends/for-you, cursor, hide/mute, subscriptions |
| `/stories/v1/*` | publish, tray, slides, expire/highlights, audience/view/replies |
| `/reels/v1/*` | publish, processing, swipe feed, react/comment/report |

Все inputs имеют bounded page size, action idempotency token для создания, server-side rate/entitlement/privacy checks и не расходуют квоту до подтверждения bytes. UI/Web/Android/iOS не создают собственные правила авторизации. Сервисная структура остаётся modular monolith с изолированными workers/queues.

## 7. Delivery order и release acceptance

Это **добавленный объём будущих работ**, а не повод считать незавершённый Messenger E2EE #59/#61 или Safety Center завершёнными. Запланировано в продуктовую линию:

1. **0.8 Social Content foundation (параллельно Living Spaces)**: S3/quotas/quarantine/migration → Post + личная стена + текст/фото/смешанные альбомы → subscriptions/friends хронологическая лента → comments/reactions/bookmarks + базовая report/moderation. Web vertical slice, затем Android/iOS через тот же API.
2. **0.9 Media & Engagement (параллельно Product Experience)**: graffiti editor, video/audio/music, async transcode/player, stories TTL/highlights, reels/feed/recommendations, privacy and economy/abuse controls. Точные контентные ограничения и платные квоты принимаются по capacity/cost data.
3. **1.0 readiness / full parity**: одинаковые согласованные сценарии публикации, просмотра, реакции, блокировки и удаления **на Web/Android/iOS**, real S3-compatible backend, no overquota races, обработка media failure/provider outage, moderation/rights, real phones/browsers, measured CPU/storage/egress. Функция может быть под feature flag до завершения этих gates, но её нельзя назвать реализованной в релизе.

Чекпоинты должны документировать code / CI / device / production отдельно, иметь реальные backend+client PR и закрывать соответствующий issue только после acceptance. Незавершённый функционал не получает статус «✅» за счёт макета.

## 8. GitHub work breakdown (source of truth)

- [Epic #134 — Social Content Platform](https://github.com/cyrox007/PubChat/issues/134).
- [#135 — S3 MediaService, upload sessions, Account quota](https://github.com/cyrox007/PubChat/issues/135).
- [#136 — Personal wall / Posts and media](https://github.com/cyrox007/PubChat/issues/136).
- [#137 — Home feed / social graph](https://github.com/cyrox007/PubChat/issues/137).
- [#138 — Graffiti editor](https://github.com/cyrox007/PubChat/issues/138).
- [#139 — Video/music/audio publishing](https://github.com/cyrox007/PubChat/issues/139).
- [#140 — Stories](https://github.com/cyrox007/PubChat/issues/140).
- [#141 — Reels / Clips](https://github.com/cyrox007/PubChat/issues/141).
- [#142 — Cross-client media QA / rights/privacy/storage](https://github.com/cyrox007/PubChat/issues/142).

Ни одна задача здесь не закрыта разработкой этого документа. Новые GitHub implementation PR обязаны ссылаться на свой issue и обновлять `docs/cross-client-delivery-status.md`, `docs/roadmap.md` и мобильные parity matrices после реального слияния.
