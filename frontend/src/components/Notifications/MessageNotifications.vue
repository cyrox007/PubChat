<template>
    <Transition name="incoming-notice">
        <aside v-if="visibleNotice" class="incoming-notice" role="status" aria-live="polite">
            <span class="incoming-notice__icon" aria-hidden="true">
                <i class="fas fa-comment-dots"></i>
            </span>
            <button class="incoming-notice__open" type="button" @click="openNotification(visibleNotice)">
                <strong>{{ heading(visibleNotice) }}</strong>
                <span>{{ description(visibleNotice) }}</span>
                <small>Открыть разговор</small>
            </button>
            <button class="incoming-notice__close" type="button"
                aria-label="Закрыть уведомление" @click="dismiss">
                <i class="fas fa-xmark" aria-hidden="true"></i>
            </button>
        </aside>
    </Transition>
</template>

<script setup>
import { computed, onUnmounted, ref, watch } from 'vue';
import { useStore } from 'vuex';
import { useRoute, useRouter } from 'vue-router';
import NotificationService from '@/API/NotificationService';
import { isViewingNotificationTarget, shouldShowForegroundNotice } from '@/utils/notificationAttention';

const store = useStore();
const route = useRoute();
const router = useRouter();
const incoming = computed(() => store.getters['messenger/getNotifications'] || []);
const visibleNotice = ref(null);
const observed = new Set(incoming.value.map((event) => event.uid));
let hideTimer = null;

const isActiveConversation = (notice) => isViewingNotificationTarget(
    notice, route.name, route.params.uid,
    store.getters['messenger/getActiveDialog'],
);

const heading = (notice) => notice.uid?.startsWith('space-reply:')
    ? 'Ответ на ваше сообщение'
    : notice.surface === 'space' ? 'Событие в пространстве' : 'Новое личное сообщение';

const description = (notice) => notice.surface === 'space'
    ? 'Откройте пространство, чтобы посмотреть сообщение.'
    : 'Откройте Messenger, чтобы прочитать сообщение.';

const dismiss = () => {
    if (hideTimer) window.clearTimeout(hideTimer);
    hideTimer = null;
    visibleNotice.value = null;
};

watch(incoming, (items) => {
    const fresh = [...items].reverse().find((item) => (
        !observed.has(item.uid) && shouldShowForegroundNotice(item, {
            visibilityState: document.visibilityState,
            routeName: route.name,
            roomUid: route.params.uid,
            activeDialog: store.getters['messenger/getActiveDialog'],
        })
    ));
    for (const item of items) if (item.uid) observed.add(item.uid);
    if (fresh) {
        dismiss();
        visibleNotice.value = fresh;
        hideTimer = window.setTimeout(dismiss, 6500);
    }
}, { deep: true });

watch(() => route.fullPath, () => {
    if (visibleNotice.value && isActiveConversation(visibleNotice.value)) dismiss();
});

const openNotification = async (notice) => {
    dismiss();
    store.commit('messenger/DISMISS_NOTIFICATION', notice.uid);
    if (notice.surface === 'space' && notice.roomUid) {
        // Navigating must work even when the read-status endpoint is unavailable.
        await router.push({ name: 'space', params: { uid: notice.roomUid } });
        if (notice.serverNotificationUid) {
            try {
                await NotificationService.markRead(notice.serverNotificationUid);
                await store.dispatch('notifications/refreshUnread');
            } catch {
                // Keep the durable notification unread so it can be retried.
            }
        }
    } else {
        if (notice.userId) store.commit('messenger/SET_ACTIVE_DIALOG', notice.userId);
        await router.push({ name: 'messenger' });
    }
};
onUnmounted(dismiss);
</script>

<style scoped>
.incoming-notice {
    position: fixed;
    top: calc(4.25rem + env(safe-area-inset-top, 0px));
    right: max(12px, env(safe-area-inset-right, 0px));
    z-index: 145;
    width: min(390px, calc(100vw - 24px));
    display: flex;
    align-items: flex-start;
    gap: var(--ui-space-3);
    padding: var(--ui-space-3);
    border: 1px solid var(--ui-border);
    border-radius: var(--ui-radius-lg);
    background: var(--ui-surface-raised);
    box-shadow: var(--ui-shadow-lg);
    color: var(--ui-text);
}
.incoming-notice__icon {
    width: 2.25rem;
    height: 2.25rem;
    flex: 0 0 auto;
    display: grid;
    place-items: center;
    border-radius: var(--ui-radius-md);
    color: var(--ui-primary);
    background: var(--ui-primary-soft);
}
.incoming-notice__open {
    flex: 1; min-width: 0;
    display: grid; gap: 4px;
    padding: 0;
    background: transparent;
    border: 0;
    text-align: left;
    color: inherit;
    cursor: pointer;
}
.incoming-notice__open strong { font-size: var(--ui-text-sm); }
.incoming-notice__open span { color: var(--ui-text-muted); line-height: 1.4; }
.incoming-notice__open small { color: var(--ui-primary); font-weight: 700; }
.incoming-notice__close {
    flex: 0 0 auto;
    width: 2rem; height: 2rem;
    display: grid; place-items: center;
    background: transparent; border: 0;
    color: var(--ui-text-muted);
    border-radius: var(--ui-radius-md); cursor: pointer;
}
.incoming-notice__close:hover { background: var(--ui-surface-muted); color: var(--ui-text); }
.incoming-notice-enter-active, .incoming-notice-leave-active {
    transition: opacity 220ms ease, transform 220ms ease;
}
.incoming-notice-enter-from, .incoming-notice-leave-to {
    opacity: 0; transform: translateY(-12px);
}
@media (max-width: 720px) {
    .incoming-notice {
        top: calc(var(--ui-mobile-topbar-height, 3.5rem) + env(safe-area-inset-top, 0px) + 8px);
        right: 12px;
    }
}
@media (prefers-reduced-motion: reduce) {
    .incoming-notice-enter-active, .incoming-notice-leave-active { transition-duration: 0.01ms; }
}
</style>
