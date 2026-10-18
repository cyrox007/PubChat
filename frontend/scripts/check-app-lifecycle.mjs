import { readFileSync } from 'node:fs';
import './check-e2ee-verification.mjs';
import './check-e2ee-directory-transparency.mjs';
import './check-call-security.mjs';
import './check-public-asset-urls.mjs';

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8');
const header = read('../src/components/HeaderComponent/index.vue');
const app = read('../src/App.vue');
const spaceNavigation = read('../src/components/Spaces/SpaceContextNavigation.vue');
const roomPanel = read('../src/components/RightSidebar/index.vue');
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
if (header.includes("name: 'space-community'") || header.includes("name: 'space-life'") || header.includes("name: 'space-support'")) {
  fail('Global header must not own space-specific navigation');
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
if (!app.includes("import CallOverlay from '@/components/Calls/CallOverlay.vue'")) {
  fail('App shell must import the global call overlay');
}
if (!app.includes('<CallOverlay />')) {
  fail('App shell must mount the global call overlay so call launcher and incoming calls stay available');
}
if (app.includes('<SpaceContextNavigation')) {
  fail('Space management navigation must live inside the room, not the app shell');
}
if (!roomPanel.includes('<SpaceContextNavigation') || !roomPanel.includes('<SpaceWorkspacePanel')) {
  fail('The room panel must own space navigation and its embedded tools');
}
for (const routeName of ['space', 'space-community', 'space-life', 'space-support']) {
  if (!spaceNavigation.includes(`name: '${routeName}'`)) {
    fail(`Space navigation must expose ${routeName}`);
  }
}
if (!notifications.includes('POLL_INTERVAL_MS') || !notifications.includes("NotificationService.sync()")) {
  fail('notification polling implementation must remain centralized in the store');
}

if (process.exitCode) process.exit(process.exitCode);
console.log('App lifecycle guard passed');
