import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
    isViewingNotificationTarget,
    shouldShowForegroundNotice,
} from '../src/utils/notificationAttention.js';

const spaceReply = { uid: 'space-reply:1', surface: 'space', roomUid: 'room-1' };
const dm = { uid: 'messenger:1', surface: 'messenger', userId: 'peer-1' };
const visible = { visibilityState: 'visible', routeName: 'people', roomUid: null, activeDialog: null };

assert.equal(shouldShowForegroundNotice(spaceReply, visible), true,
    'Reply to my Space message must alert from other sections');
assert.equal(shouldShowForegroundNotice(spaceReply, {
    ...visible, routeName: 'space', roomUid: 'room-1',
}), false, 'Visible quoted Space should not duplicate its message');
assert.equal(shouldShowForegroundNotice(spaceReply, {
    ...visible, routeName: 'space', roomUid: 'room-2',
}), true, 'Different Space must still alert');
assert.equal(shouldShowForegroundNotice(spaceReply, {
    ...visible, visibilityState: 'hidden',
}), false, 'Background page uses Web Push, not in-app toast');
assert.equal(shouldShowForegroundNotice(spaceReply, {
    ...visible, routeName: 'notifications',
}), false, 'Already reading Activity');
assert.equal(shouldShowForegroundNotice(dm, visible), true);
assert.equal(isViewingNotificationTarget(dm, 'messenger', null, 'peer-1'), true);
assert.equal(shouldShowForegroundNotice(dm, {
    ...visible, routeName: 'messenger', activeDialog: 'peer-1',
}), false, 'Do not interrupt the visible DM');
assert.equal(shouldShowForegroundNotice(dm, {
    ...visible, routeName: 'messenger', activeDialog: 'peer-2',
}), true);

const source = (path) => readFileSync(new URL(path, import.meta.url), 'utf8');
const app = source('../src/App.vue');
const webPush = source('../public/service-worker.js');
const notificationView = source('../src/views/NotificationsView.vue');
const store = source('../src/stores/notifications.js');
const toast = source('../src/components/Notifications/MessageNotifications.vue');
const messenger = source('../src/stores/messenger.js');

assert.match(app, /handleServiceWorkerNotification/,
    'Focused PWA push must reach the foreground shell when socket is down');
assert.match(webPush, /pubchat:push-received/,
    'Service Worker must forward suppressed focused push to the app');
assert.match(toast, /deep: true/,
    'Vuex in-place notification pushes must trigger the toast observer');
assert.doesNotMatch(app, /<ReplyNotifications\s*\/>/,
    'Do not mount the old duplicate notification overlay');
assert.match(notificationView, /item\.kind === 'space_reply' \? 'space' : 'space-life'/,
    'Clicking a direct reply must open the Space conversation, not its Life tab');
assert.match(store, /POLL_INTERVAL_MS = 30000/,
    'Foreground fallback updates should run within a reasonable interval');
assert.match(store, /dispatch\('pollInbox'\)/,
    'The foreground fallback should read the durable inbox instead of writing reminders');
assert.match(store, /NotificationService\.list\(\{ limit: 50 \}\)/,
    'Foreground recovery must read the first-party personal notification ledger');
assert.match(store, /observedReplyIds !== null/,
    'Historical unread must be primed silently rather than reannounced');
assert.match(messenger, /serverNotificationUid: data\.notification_uid/,
    'Realtime reply should retain the durable notification ID for read receipts');

console.log('Foreground/web push Space and DM notification regression guard passed');
