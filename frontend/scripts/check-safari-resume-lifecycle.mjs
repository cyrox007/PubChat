import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8');
const app = read('../src/App.vue');
const user = read('../src/stores/user.js');
const entry = read('../src/main.js');
const room = read('../src/stores/chat.js');
const messenger = read('../src/stores/messenger.js');

// This is a source-level lifecycle contract, paired with executed Vuex socket
// regression tests. It is NOT evidence of a successful real-device iOS test.
assert.match(app, /document\.addEventListener\('visibilitychange', handleVisibilityChange\)/,
  'Returning from Safari background must be observed');
assert.match(app, /window\.addEventListener\('pageshow', handlePageShow\)/,
  'BFCache restoration must be observed on iOS');
assert.match(app, /if \(event\.persisted\) reconnectAfterWake\(true\)/,
  'BFCache wake must reissue fresh one-time socket tickets');
assert.match(app, /IOS_WAKE_RECONNECT_AFTER_MS = 45000/,
  'Long background suspension requires a bounded recovery policy');
assert.match(app, /store\.dispatch\('messenger\/disconnectMessenger'\)/);
assert.match(app, /store\.dispatch\('chat\/disconnectSocket'\)/);
assert.match(app, /store\.dispatch\('notifications\/pollInbox'\)/,
  'Wake must refresh pending notifications without forcing reminder sync');
assert.match(app, /Promise\.allSettled\(\[/,
  'Messenger handshake must not delay a room socket or notification refresh');
assert.match(app, /store\.getters\.isIdentityValidated/,
  'The app shell must avoid duplicate verified /me fetches after startup');
assert.match(user, /identityValidated: false/,
  'Cached identity is not verified for the new browser tab');
assert.match(user, /commit\('setIdentityValidated', true\)/,
  'Only verified server identity should skip bootstrap sync');
assert.match(entry, /await store\.dispatch\('restoreSessionAccess'\)/,
  'Browser must obtain a fresh access token before protected route mount');
assert.match(room, /Remote 1000 still needs reconnect/,
  'Server-initiated normal room closure must recover');
assert.match(messenger, /Remote normal 1000 closure is not user intent/,
  'Server-initiated normal Messenger closure must recover');

console.log('Safari lifecycle and authenticated bootstrap source contract: OK');
