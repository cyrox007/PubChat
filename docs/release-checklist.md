# PubChat release checklist

## До version bump

- scope заморожен, P0/P1 blockers отсутствуют;
- migrations reviewed, `alembic heads` показывает одну head;
- backend compile/import и contract tests проходят;
- для DB-sensitive slice clean PostgreSQL `alembic upgrade head` проходит;
- `alembic check` не показывает model/schema drift;
- PostgreSQL integration smoke проходит там, где slice затрагивает persistence/worker behavior;
- frontend production build проходит;
- production dependency audits (`npm audit --omit=dev --audit-level=high` + `pip-audit`) проходят без unresolved vulnerability;
- browser-sensitive slice проходит Playwright Chromium/Firefox/WebKit/mobile gate;
- privacy/permissions/data self-review завершён;
- пользовательская и техническая документация обновлена;
- CI зелёный на exact functional head;
- если срез затрагивает Posts/Stories/Reels/S3: проверены реальные S3-compatible provider + quota reservation/reconciliation, private/public ACL, права/модерация медиа, просроченные Stories, revocation/cached URL и cross-client code/CI/device states из [Social Content & Media v1](social-content-media-platform-v1.md); до готовности endpoint недоступен публично или находится под feature flag.

## Versioned gate

Только после первого успешного gate:

- обновить `VERSION`;
- зафиксировать release entry в `CHANGELOG.md`;
- синхронизировать versioning docs;
- снова запустить CI на exact versioned head;
- проверить совпадение backend/frontend версии;
- только после второго зелёного gate переводить PR в ready и merge.

## Перед deployment

- backup данных;
- migration rehearsal для рискованных изменений на репрезентативной копии schema/data;
- проверить PostgreSQL/Redis/configuration;
- собрать frontend;
- проверить `/health` и `/service/version`;
- выполнить smoke test registration/login/session reload/logout, Space realtime и DM.
- если email/Web Push delivery включены — проверить `python -m workers.external_delivery_observability --window-hours 24 --require-healthy` и разобрать stale backlog/expired claims до открытия трафика;

Clean-database migration CI не заменяет backup/restore drill и rehearsal на legacy data перед реальным production deployment.

**1.0 Social Content gate (запланированный объём):** готовность текст/фото/mixed/graffiti/video/audio Posts, personal wall, feed, Stories и Reels оценивается по одинаковым server-authorized пользовательским сценариям на Web/Android/iOS, real-device QA и устойчивой стоимости object storage/CDN. Наличие ТЗ не является выполнением release gate.

Переход alpha → beta → stable зависит от readiness gate, а не даты или числа commits.
