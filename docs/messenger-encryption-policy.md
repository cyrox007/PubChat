# Messenger encryption policy

PubChat supports two actual transports for direct messages: ordinary server-readable Messenger messages and per-device E2EE envelopes. Encryption is a conversation policy, not an attribute that can be retroactively applied to existing history.

## System policy

Set `MESSENGER_E2EE_POLICY` on the backend to one of:

- `disabled` — direct conversations use plaintext transport; E2EE sends are rejected by the backend.
- `optional` — E2EE can be explicitly enabled only by an Account that has earned the E2EE privilege.
- `required` — all new direct-message sends must use E2EE; plaintext WebSocket sends are rejected.

The default is `optional`.

An unconfigured optional conversation starts in `plaintext`. There is no automatic crypto-capable-peer upgrade anymore, because that would bypass the earned-privilege gate.

Changing the system policy does not rewrite the stored per-conversation preference. `disabled` and `required` override it while active; switching the system back to `optional` restores the stored choice.

## Earned E2EE activation privilege

Optional E2EE is a privilege, not a default Account capability. The backend allows a transition into `e2ee` only when at least one of these conditions is true for the Account performing the change:

- current Account reputation label is `established` or `trusted`;
- current platform role is elevated above ordinary `user`: today this means `moderator` or `admin`.

Reputation is Account-level. The current identity model also stores platform roles at Account level rather than Persona level, so the elevated-role override is enforced against the Account behind the active Persona. A future Persona-specific role system should be wired into the same policy function instead of duplicating the rule in the client.

`unknown`, `developing`, `concerning`, expired assessment, or no assessment do not unlock optional E2EE by themselves.

The privilege gates **activation**, not retroactive confidentiality. If a conversation was already explicitly set to E2EE and the Account's reputation later changes, PubChat does not silently downgrade that conversation to plaintext. The user can still switch it back to plaintext; switching into E2EE again requires current eligibility.

The system-level `required` policy is an administrative override and does not depend on reputation or role.

## Per-conversation preference

`private_conversation_encryption` stores one canonical Account pair and only the selected mode (`plaintext|e2ee`) plus audit metadata. The preference is shared by both participants and all of their devices.

API:

- `GET /messenger/conversations/{peer_uid}/encryption`
- `PUT /messenger/conversations/{peer_uid}/encryption` with `{ "mode": "plaintext" }` or `{ "mode": "e2ee" }`

The response exposes:

- `system_policy`
- `configured_mode`
- `effective_mode`
- `can_change`
- `can_enable_e2ee`
- `e2ee_eligible`
- `e2ee_eligibility_reason`
- `reputation_label`
- `elevated_role`
- `positive_reputation_labels`
- `crypto_ready`
- active crypto-device counts for both sides

A mode can be changed through the API only while system policy is `optional` and the existing DM privacy/block policy allows the conversation. A request to enable E2EE without the earned privilege fails with HTTP 403 / `e2ee_privilege_required`.

## Fail-closed transport rules

The client-side switch is not a security boundary. Both transports are independently enforced on the server:

- plaintext Messenger WebSocket frames are consumed and rejected when effective mode is `e2ee`;
- encrypted `/crypto/v1/messages` sends are rejected when effective mode is `plaintext` or E2EE is disabled;
- legacy HTTP `/messages/v2/messenger/{uid}` text edits, `/reply` and `/forward` to Messenger must also assert the **current target conversation** is in effective `plaintext` mode before writing; switching a conversation to E2EE cannot be bypassed through REST actions;
- editing/replying to an existing `content_type=e2ee` envelope using plaintext and forwarding such envelopes without device-specific ciphertext envelopes are refused instead of fabricating a cleartext message or a non-decryptable row;
- `required`/explicit `e2ee` with missing crypto devices blocks the send instead of silently downgrading to plaintext;
- optional E2EE activation is rejected server-side unless the Account has positive reputation or an elevated platform role.

The browser checks the current policy before deciding whether a peer should be treated as an E2EE target. This keeps text and encrypted attachments on the same conversation mode.

## History semantics

Switching a conversation changes only future sends. Existing rows keep the transport they were actually sent with:

- old plaintext remains plaintext;
- old E2EE rows remain ciphertext envelopes and still require local keys to decrypt.

PubChat must never label an old plaintext row as encrypted merely because the current conversation mode is E2EE.

## Spaces

This policy applies to direct Messenger conversations. Living Space chats are not automatically converted to E2EE. A future private/group Space encryption design needs a group-key protocol and separate moderation/product rules rather than reusing the 1:1 switch blindly.
