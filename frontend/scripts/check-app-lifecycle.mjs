import { readFileSync } from 'node:fs';
import './check-e2ee-verification.mjs';
import './check-e2ee-directory-transparency.mjs';
import './check-call-security.mjs';
import './check-public-asset-urls.mjs';

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8');
const header = read('../src/components/HeaderComponent/index.vue');
const app = read('../src/App.vue');
const store = read('../src/stores/index.js');
const notifications = read('../src/stores/notifications.js');

const fail = (message) => {
  console.error(`App lifecycle guard failed: ${message}`);
  process.exitCode = 1;
};

if (header.includes('NotificationService')) {
  fail('Header must not own notification network calls');
}
if (header.includes('setInterval(') || header.includes('setTimeout(')) {
  fail('Header must not own polling timers');
}
if (!header.includes("store.getters['notifications/unread']")) {
  fail('Header must render unread state from the shared notification store');
}
if (!store.includes('notifications: notificationsStore')) {
  fail('notification Vuex module must be registered');
}
if (!app.includes("notifications/startPolling") || !app.includes("notifications/stopPolling")) {
  fail('App shell must own notification polling lifecycle');
}
if (!app.includes('authenticatedBootstrap')) {
  fail('authenticated bootstrap must remain deduplicated');
}
if (!notifications.includes('POLL_INTERVAL_MS') || !notifications.includes("NotificationService.sync()")) {
  fail('notification polling implementation must remain centralized in the store');
}

if (process.exitCode) process.exit(process.exitCode);
console.log('App lifecycle guard passed');
