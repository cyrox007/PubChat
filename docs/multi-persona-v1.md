# PubChat 0.7 — Multi-Persona (session foundation)

## Identity boundary

**Account != Persona.** Credentials, tokens, sessions, moderation, bans,
trust, achievements, friendships and blocks remain attached to Account.
Changing a public Persona never creates a second Account or elevates access.

## Implemented initial contract

- `GET /identity/v2/personas` — only Personas owned by authenticated Account,
  with `active_persona_uid` for the current session
- `POST /identity/v2/personas` — creates an additional Persona;
  max **3** per Account, globally unique handle, display name and social intent
- `POST /identity/v2/personas/{persona_uid}/activate` — chooses a Persona for the
  **current IdentitySession**, not all devices; rejects another Account's UID
- `GET /identity/v2/me` and `PATCH /persona` — use that session's active Persona
- `PATCH /privacy` — primary Persona only while messages/contact policies
  remain Account/primary-scoped; attempting to relax secondary privacy fails
- Legacy sessions without `session_uid` keep the primary Persona; switching
  requires a server-validated, non-revoked IdentitySession

Both `IdentitySession.active_persona_uid` and DB partial uniqueness of
Account primary Persona are installed in the additive Alembic migration.
NULL selection means primary Persona; a new login defaults to primary.

## Privacy and compatibility restrictions

**Secondary Persona is private by default:** profile_visibility=private and
dm_policy=nobody. It is not in public discovery, Account public profile,
people-batch, conversations, realtime author projection, Space identity or
client directory, even after activation.

This is intentionally a **private session-selection foundation**, not the
full public Multi-Persona release. Publishing a secondary Persona requires
future privacy-aware Persona-by-UID endpoints and changes to attribution,
search, messaging and moderation. Do not silently display private Persona
details to a contact based solely on the public Account UID.

Web, Android and iOS can create/list/select with matching API semantics;
they must not claim another identity on incoming messages or grant new DM
permissions after switching. Client view of the user's own active Persona
may be private and differs from the Account's current public (primary) card.

## Threat model and verification

- Cross-account Persona activation must return 404/401, never the other
  Persona projection.
- Expired/revoked session must fail, even with a valid account UID.
- Account-level suspension and privilege restrictions are checked before
  Persona operations, not inferred from client state.
- Concurrent create across the same Account is serialized by a row lock;
  duplicate handles are rejected with 409.
- Never log access/refresh tokens in Persona actions.
- Creating secondary Persona does not add Credential or IdentitySession.
- On logout, all per-session selection is inaccessible until next login;
  another device's Persona selection is unchanged.
- Device acceptance: select one secondary on Web, keep primary in Android
  session, select another on iOS, verify account-level blocks still work.

## Remaining 0.7 work

Persona-specific public URLs, avatar appearance and discoverability,
private-vs-public separation/consent, ownership-safe deactivation/deletion,
realtime/DM/Spaces Persona attribution, cross-device privacy tests and
conflict behavior are **not** covered by this slice.
