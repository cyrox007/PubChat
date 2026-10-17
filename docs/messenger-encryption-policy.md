# Messenger encryption policy

PubChat supports two actual transports for direct messages: ordinary server-readable Messenger messages and per-device E2EE envelopes. Encryption is a conversation policy, not an attribute that can be retroactively applied to existing history.

## System policy

Set `MESSENGER_E2EE_POLICY` on the backend to one of:

- `disabled` — direct conversations use plaintext transport; E2EE sends are rejected by the backend.
- `optional` — participants may select `plaintext` or `e2ee` for each direct conversation.
- `required` — all new direct-message sends must use E2EE; plaintext WebSocket sends are rejected.

The default is `optional`.

For rollout compatibility, an optional conversation with no explicit stored preference preserves the previous behavior: a peer with active crypto devices uses E2EE; a peer without crypto devices remains plaintext. Once either participant explicitly selects a mode, that shared conversation preference is authoritative.

Changing the system policy does not rewrite the stored per-conversation preference. `disabled` and `required` override it while active; switching the system back to `optional` restores the stored choice.

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
- `crypto_ready`
- active crypto-device counts for both sides

A mode can be changed through the API only while system policy is `optional` and the existing DM privacy/block policy allows the conversation.

## Fail-closed transport rules

The client-side switch is not a security boundary. Both transports are independently enforced on the server:

- plaintext Messenger WebSocket frames are consumed and rejected when effective mode is `e2ee`;
- encrypted `/crypto/v1/messages` sends are rejected when effective mode is `plaintext` or E2EE is disabled;
- `required`/explicit `e2ee` with missing crypto devices blocks the send instead of silently downgrading to plaintext.

The browser checks the current policy before deciding whether a crypto-capable peer should be treated as an E2EE target. This keeps text and encrypted attachments on the same conversation mode.

## History semantics

Switching a conversation changes only future sends. Existing rows keep the transport they were actually sent with:

- old plaintext remains plaintext;
- old E2EE rows remain ciphertext envelopes and still require local keys to decrypt.

PubChat must never label an old plaintext row as encrypted merely because the current conversation mode is E2EE.

## Spaces

This policy applies to direct Messenger conversations. Living Space chats are not automatically converted to E2EE. A future private/group Space encryption design needs a group-key protocol and separate moderation/product rules rather than reusing the 1:1 switch blindly.
