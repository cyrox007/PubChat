# Space Categories: rollout and acceptance checklist

Status: 2026-10-19. Tracking: [PubChat #122](https://github.com/cyrox007/PubChat/issues/122).
Reference: eight approved PNG boards dated 2026-10-18 (restored as described in `docs/design/approved-2026-10-18/README.md`).

## Scope / compatibility

- Web/backend taxonomy shipped in [#123](https://github.com/cyrox007/PubChat/pull/123).
- Schema revision: `x2m8q6l11001` (parents `w1l7p5k00001`).
- Tables: `space_categories` (stable slug and soft archive), `space_category_assignments` (max 3 enforced by API), `space_category_audit` (administrative changes).
- The seven seeded categories correspond to the approved design. **Existing Spaces receive no automatic assignments**. Existing `purpose` and `tags` are separate and must not be rewritten to guess categories.
- Mobile clients consume `GET /spaces/v1/categories` and `GET /spaces/v1?category=slug`. iOS creation and Android/iOS owner editing follow via native PRs, but must only be exposed once the server revision is deployed.

## Before production migration

1. Confirm the deployed server is based on a tested and reviewed `main` commit and all mandatory GitHub CI checks are green.
2. Take a verified, restorable backup of the **production PostgreSQL database and uploads**. Do not discard the backup after an apparently successful migration.
3. Rehearse the migration on a copy of representative legacy data. Verify that pre-existing Spaces, their `purpose`, `tags`, memberships and visibility remain unchanged.
4. From the configured backend virtualenv, run `alembic heads` and verify **exactly one migration head**, containing or succeeding `x2m8q6l11001`.
5. Check server preflight, PostgreSQL, Redis, disk headroom and migration privileges as documented in `docs/operations.md`. Do not run a manual full backend restart that bypasses socket-activated rolling deploy.

## Deploy

On the actual managed host, using the existing authorized operator account:

```bash
cd /home/projects/pubchat
./update.sh
```

This delegates to `ops/deploy.sh` and runs dependency sync, migrations, staged frontend publication and rolling reload with a readiness gate. Do not invoke `alembic upgrade head` a second time unless diagnosing a failed stage according to the operator procedures. Do not claim deployment succeeded merely because `git pull` or frontend build succeeded.

## Required production smoke

With a legitimate test account and one authorized administrator:

- Check `/health/ready` and `/service/version` on the deployed backend and confirm deployed revision.
- Confirm `alembic current` shows `x2m8q6l11001` or a later single-head revision.
- On the administrative **Категории пространств** page: verify seven seed rows. Create a test category, change its name/position, archive and restore it; inspect the audit history. Ensure an ordinary member cannot call any admin category mutation endpoint (expected 403).
- As a Space owner, create a disposable Space and assign two categories. Verify the Space response includes `category_slugs`. Change to three, then clear all assignments; confirm the server stores each change. As a non-owner, PATCH of `category_slugs` must fail (403). Try a malformed/inactive slug and more than three slugs: expect validation failure, with no partial category changes.
- Check Discovery filters the actual server-side Space set by category. Confirm old Spaces with no assignments remain visible when the category filter is cleared, and that `purpose` and free `tags` remain unchanged.
- Check Web at 320, 344 and 390 CSS px for clipping/overflow, including the category selection sheet and Space creator.
- On physical Android and iOS devices, test catalog filtering, owner category editing and (iOS) new Space creation; verify 48dp/44pt controls, keyboard, error/retry, permissions and the approved boards. **Automated CI is not physical-device visual acceptance.**

### Deployment ordering

Deploy the **backend migration and API first**, then use new Android/iOS binaries. Old clients remain compatible with Spaces that have or lack `category_slugs`. Never route a client requiring the new endpoints to an old backend instance during a rolling transition.

## Failure and rollback

- If migration, readiness, API contract or data-integrity smoke fails: halt rollout and preserve the database backup, deploy logs and the deployed revision. Avoid repeated blind `./update.sh` attempts.
- **Do not downgrade `x2m8q6l11001` casually**: its Alembic `downgrade()` drops category, assignment and audit tables, irreversibly discarding any changes made after migration. Restore from the validated backup when a data rollback is authorized, or perform an explicit forward-fix with the compatible schema retained.
- App code rollback is not automatically a database rollback. Keep the additive schema if older server code tolerates it; rehearse the exact rollback sequence before executing.
- Track pending screenshot approval, server smoke results and native release build versions in issue #122, and leave it open until verified.

## Operators and privacy

Do not store production credentials, session cookies, private user data or test account secrets in screenshots, logs attached to GitHub or this document. Use disposable test Spaces and remove test data after verifying the audit obligations.
