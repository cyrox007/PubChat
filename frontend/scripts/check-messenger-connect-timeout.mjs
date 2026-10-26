import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

// Exercise the real Vuex action logic with controlled WebSocket and timers.
const scheduled = new Map();
let nextId = 0;
const realTimers = {
  setTimeout: globalThis.setTimeout,
  clearTimeout: globalThis.clearTimeout,
  setInterval: globalThis.setInterval,
  clearInterval: globalThis.clearInterval,
};
globalThis.setTimeout = (fn, ms) => {
  const id = ++nextId;
  scheduled.set(id, { fn, ms });
  return id;
};
globalThis.clearTimeout = (id) => scheduled.delete(id);
globalThis.setInterval = () => ++nextId;
globalThis.clearInterval = () => {};
globalThis.WebSocket = { CONNECTING: 0, OPEN: 1 };

let resolveTicket;
let ticketRequests = 0;
globalThis.__messengerApi = {
  prepareSocket: () => {
    ticketRequests += 1;
    return new Promise((resolve) => { resolveTicket = resolve; });
  },
};
const source = readFileSync(new URL('../src/stores/messenger.js', import.meta.url), 'utf8')
  .replace(/^import[\s\S]*?from\s+['"][^'"]+['"];?\s*/gm, '');
const { default: module } = await import('data:text/javascript;base64,'
  + Buffer.from('const RealtimeService=globalThis.__messengerApi;\n' + source).toString('base64'));
const state = structuredClone(module.state);
const events = [];
const ctx = {
  state,
  commit: (key, value) => module.mutations[key](state, value),
  dispatch: (key, value) => { events.push([key, value]); },
};
try {
  const pending = module.actions.connectMessenger(ctx);
  assert.equal(state.connectionState, 'connecting');
  await module.actions.connectMessenger(ctx);
  module.actions.reconnectIfNeeded(ctx);
  assert.equal(ticketRequests, 1, 'Only one pending ticket is allowed on reconnect and foreground');
  const watchdog = [...scheduled.values()].find((x) => x.ms === 15000);
  assert.ok(watchdog, 'Messenger must bound its ticket+socket+auth handshake');
  watchdog.fn();
  assert.equal(events.at(-1)[0], 'scheduleReconnect');
  let lateClosed = false;
  resolveTicket({ socket: { close() { lateClosed = true; } }, ticket: 'late' });
  await pending;
  assert.ok(lateClosed, 'A stale ticket must be closed before the socket can be installed');

  let closes = 0;
  let sends = 0;
  let socket = {
    readyState: WebSocket.OPEN,
    send() { sends += 1; },
    close() { closes += 1; },
  };
  globalThis.__messengerApi.prepareSocket = async () => ({ socket, ticket: 'fresh' });
  await module.actions.connectMessenger(ctx);
  await module.actions.connectMessenger(ctx);
  assert.equal(state.socket, socket);
  assert.equal(closes, 0, 'Duplicate bootstrap must preserve a healthy socket');
  socket.onopen();
  assert.equal(sends, 1, 'An auth frame should be sent exactly once');
  socket.onmessage({ data: JSON.stringify({ type: 'realtime_ready' }) });
  assert.equal(state.connectionState, 'connected');
  assert.equal(scheduled.size, 0, 'Successful handshake must clear the 15s watchdog');
  socket.onclose({ code: 1000, reason: 'remote server rolling reload' });
  assert.equal(events.at(-1)[0], 'scheduleReconnect',
    'Unexpected remote 1000 must reconnect even if it is a normal WebSocket closure');

  socket = { readyState: WebSocket.OPEN, send() {}, close() {} };
  globalThis.__messengerApi.prepareSocket = async () => ({ socket, ticket: 'new' });
  await module.actions.connectMessenger(ctx);
  module.actions.disconnectMessenger(ctx);
  assert.equal(state.connectionState, 'idle');
  const previous = events.length;
  socket.onclose({ code: 1000, reason: 'Client disconnect' });
  assert.equal(events.length, previous, 'An explicit local disconnect must not restart a socket');
  assert.equal([...scheduled.values()].some((timer) => timer.ms === 15000), false);
  console.log('Messenger reconnect, Safari handshake watchdog, duplicate tickets and remote 1000: OK');
} finally {
  Object.assign(globalThis, realTimers);
}
