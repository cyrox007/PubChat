<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useStore } from 'vuex';

import HeaderComponent from './components/HeaderComponent/index.vue';
import CallOverlay from '@/components/Calls/CallOverlay.vue';
import ReplyNotifications from '@/components/Notifications/ReplyNotifications.vue';
import MessageNotifications from './components/Notifications/MessageNotifications.vue';
import PwaInstallPrompt from '@/components/Pwa/PwaInstallPrompt.vue';
import PwaUpdateNotice from '@/components/Pwa/PwaUpdateNotice.vue';

const store = useStore();
const route = useRoute();
const router = useRouter();
const networkOnline = ref(navigator.onLine);
const bootstrapError = ref(false);
let authenticatedBootstrap = null;
let bootstrapRetryTimer = null;
let bootstrapRetryAttempt = 0;
const routePending = ref(false);
let routeStartTimer = null;
let routeFinishTimer = null;
let routeVisibleAt = 0;

const ROUTE_PROGRESS_DELAY = 90;
const ROUTE_PROGRESS_MIN_VISIBLE = 180;
const SPACE_CONTEXT_ROUTES = new Set(['space', 'space-community', 'space-life', 'space-support', 'space-moderation']);

const BOOTSTRAP_RETRY_DELAYS = [1000, 2000, 5000, 10000, 30000];
const TRANSIENT_BOOTSTRAP_STATUSES = new Set([502, 503, 504]);
const spaceContextUid = computed(() => {
	if (!SPACE_CONTEXT_ROUTES.has(String(route.name || ''))) return '';
	return String(route.params.uid || '');
});

const clearBootstrapRetry = () => {
	if (bootstrapRetryTimer) {
		window.clearTimeout(bootstrapRetryTimer);
		bootstrapRetryTimer = null;
	}
};

const clearRouteTimers = () => {
	if (routeStartTimer) {
		window.clearTimeout(routeStartTimer);
		routeStartTimer = null;
	}
	if (routeFinishTimer) {
		window.clearTimeout(routeFinishTimer);
		routeFinishTimer = null;
	}
};

const startRouteProgress = () => {
	if (routeFinishTimer) {
		window.clearTimeout(routeFinishTimer);
		routeFinishTimer = null;
	}
	if (routePending.value || routeStartTimer) return;
	routeStartTimer = window.setTimeout(() => {
		routeStartTimer = null;
		routeVisibleAt = performance.now();
		routePending.value = true;
	}, ROUTE_PROGRESS_DELAY);
};

const finishRouteProgress = () => {
	if (routeStartTimer) {
		window.clearTimeout(routeStartTimer);
		routeStartTimer = null;
	}
	if (!routePending.value) return;
	const elapsed = performance.now() - routeVisibleAt;
	const remaining = Math.max(0, ROUTE_PROGRESS_MIN_VISIBLE - elapsed);
	if (routeFinishTimer) window.clearTimeout(routeFinishTimer);
	routeFinishTimer = window.setTimeout(() => {
		routeFinishTimer = null;
		routePending.value = false;
	}, remaining);
};

const removeRouteBeforeHook = router.beforeEach((to, from) => {
	if (to.fullPath !== from.fullPath) startRouteProgress();
});

const removeRouteAfterHook = router.afterEach(() => {
	finishRouteProgress();
});

const removeRouteErrorHook = router.onError(() => {
	finishRouteProgress();
});

const connectionNotice = computed(() => {
	if (!store.getters.isAuth) return null;
	if (!networkOnline.value) {
		return {
			tone: 'warning',
			title: 'Вы офлайн',
			message: 'PubChat сохранит текущий экран и восстановит разговоры, когда сеть вернётся.',
		};
	}

	const roomState = store.getters['chat/getConnectionState'];
	const messengerState = store.getters['messenger/getConnectionState'];
	if (['reconnecting', 'offline'].includes(roomState) || ['reconnecting', 'offline'].includes(messengerState)) {
		return {
			tone: 'info',
			title: 'Восстанавливаем связь',
			message: 'Можно оставаться в приложении — повторное подключение выполняется автоматически.',
		};
	}
	if (bootstrapError.value) {
		return {
			tone: 'danger',
			title: 'Сервис временно недоступен',
			message: 'Интерфейс остаётся доступным. PubChat повторит подключение автоматически.',
		};
	}
	return null;
});

const stopAuthenticatedServices = async () => {
	store.dispatch('notifications/stopPolling');
	store.dispatch('notifications/clear');
	await store.dispatch('messenger/disconnectMessenger');
	await store.dispatch('chat/disconnectSocket');
};

const bootstrapAuthenticatedServices = async () => {
	await store.dispatch('syncIdentity');
	await Promise.all([
		store.dispatch('messenger/connectMessenger'),
		store.dispatch('notifications/sync').catch(() => null),
	]);
	store.dispatch('notifications/startPolling');
	const room = store.getters['chat/getCurrentRoom'];
	if (room?.uid) await store.dispatch('chat/connectSocket', room.uid);
	bootstrapError.value = false;
	bootstrapRetryAttempt = 0;
	clearBootstrapRetry();
};

const scheduleBootstrapRetry = () => {
	if (bootstrapRetryTimer || !store.getters.isAuth || !networkOnline.value) return;
	const delay = BOOTSTRAP_RETRY_DELAYS[Math.min(bootstrapRetryAttempt, BOOTSTRAP_RETRY_DELAYS.length - 1)];
	bootstrapRetryAttempt += 1;
	bootstrapRetryTimer = window.setTimeout(() => {
		bootstrapRetryTimer = null;
		if (store.getters.isAuth && networkOnline.value) ensureSessionAndConnect();
	}, delay);
};

const ensureSessionAndConnect = async () => {
	if (!store.getters.isAuth) return;
	if (authenticatedBootstrap) return authenticatedBootstrap;

	authenticatedBootstrap = bootstrapAuthenticatedServices()
		.catch((error) => {
			const status = error.response?.status;
			if (status === 401) return;

			bootstrapError.value = true;
			if (!error.response || TRANSIENT_BOOTSTRAP_STATUSES.has(status)) {
				scheduleBootstrapRetry();
			}
		})
		.finally(() => {
			authenticatedBootstrap = null;
		});

	return authenticatedBootstrap;
};

const handleSessionExpired = async () => {
	clearBootstrapRetry();
	bootstrapRetryAttempt = 0;
	await stopAuthenticatedServices();
	await store.dispatch('clearUser');
	if (router.currentRoute.value.name !== 'login') {
		await router.replace({ name: 'login', query: { reason: 'session' } });
	}
};

const handleOffline = () => {
	networkOnline.value = false;
	clearBootstrapRetry();
};

const handleOnline = () => {
	networkOnline.value = true;
	bootstrapError.value = false;
	bootstrapRetryAttempt = 0;
	clearBootstrapRetry();
	if (!store.getters.isAuth) return;
	ensureSessionAndConnect();
	store.dispatch('messenger/reconnectIfNeeded');
	store.dispatch('chat/reconnectIfNeeded');
	store.dispatch('notifications/sync').catch(() => null);
};

onMounted(async () => {
	await store.dispatch('initializeUser');
	window.addEventListener('pubchat:session-expired', handleSessionExpired);
	window.addEventListener('offline', handleOffline);
	window.addEventListener('online', handleOnline);
	await ensureSessionAndConnect();
});

onUnmounted(() => {
	clearBootstrapRetry();
	clearRouteTimers();
	removeRouteBeforeHook?.();
	removeRouteAfterHook?.();
	removeRouteErrorHook?.();
	store.dispatch('notifications/stopPolling');
	window.removeEventListener('pubchat:session-expired', handleSessionExpired);
	window.removeEventListener('offline', handleOffline);
	window.removeEventListener('online', handleOnline);
});

watch(() => store.getters.isAuth, (isAuthenticated, wasAuthenticated) => {
	if (isAuthenticated && !wasAuthenticated) {
		ensureSessionAndConnect();
	} else if (!isAuthenticated && wasAuthenticated) {
		clearBootstrapRetry();
		bootstrapRetryAttempt = 0;
		stopAuthenticatedServices();
	}
});
</script>

<template>
	<div class="app-shell">
		<ReplyNotifications />
		<MessageNotifications />
		<CallOverlay />
		<HeaderComponent />
		<PwaInstallPrompt />
		<PwaUpdateNotice />

		<Transition name="route-progress">
			<div v-if="routePending" class="route-progress" role="status" aria-live="polite" aria-label="Открываем раздел">
				<span class="route-progress__bar" aria-hidden="true"></span>
			</div>
		</Transition>

		<transition name="fade">
			<div
				v-if="connectionNotice"
				class="connection-notice"
				:class="`connection-notice--${connectionNotice.tone}`"
				role="status"
				aria-live="polite"
			>
				<div class="connection-notice__pulse" aria-hidden="true"></div>
				<div class="connection-notice__content">
					<strong>{{ connectionNotice.title }}</strong>
					<span>{{ connectionNotice.message }}</span>
				</div>
			</div>
		</transition>

		<div class="container app-content" :aria-busy="routePending ? 'true' : 'false'">
			<RouterView v-slot="{ Component, route: routedView }">
				<Transition name="ui-route">
					<div :key="spaceContextUid ? `space:${spaceContextUid}` : routedView.fullPath" class="route-view-frame">
						<component :is="Component" />
					</div>
				</Transition>
			</RouterView>
		</div>
	</div>
</template>

<style scoped>
.app-shell { min-height: 100dvh; }
.app-content { position: relative; margin-top: var(--ui-space-2); }
.route-view-frame { position: relative; width: 100%; min-width: 0; }
.route-progress { position: fixed; inset: 0 0 auto; z-index: 1800; height: 3px; overflow: hidden; pointer-events: none; background: color-mix(in srgb, var(--ui-primary) 10%, transparent); }
.route-progress__bar { position: absolute; inset: 0 auto 0 0; width: 38%; border-radius: var(--ui-radius-pill); background: var(--ui-primary); box-shadow: 0 0 12px color-mix(in srgb, var(--ui-primary) 36%, transparent); animation: route-progress 1s var(--ui-ease-out) infinite; }
.route-progress-enter-active, .route-progress-leave-active { transition: opacity var(--ui-motion-fast) var(--ui-ease); }
.route-progress-enter-from, .route-progress-leave-to { opacity: 0; }
.connection-notice { position: fixed; top: var(--ui-space-3); left: 50%; z-index: 1000; width: min(calc(100% - 24px), 640px); display: flex; align-items: center; gap: var(--ui-space-3); padding: var(--ui-space-3) var(--ui-space-4); transform: translateX(-50%); border: 1px solid var(--ui-border); border-radius: var(--ui-radius-lg); background: var(--ui-surface-raised); box-shadow: var(--ui-shadow-lg); color: var(--ui-text); }
.connection-notice--warning { border-color: color-mix(in srgb, var(--ui-warning) 32%, var(--ui-border)); }
.connection-notice--danger { border-color: color-mix(in srgb, var(--ui-danger) 32%, var(--ui-border)); }
.connection-notice--info { border-color: color-mix(in srgb, var(--ui-info) 32%, var(--ui-border)); }
.connection-notice__pulse { width: 0.625rem; height: 0.625rem; flex: 0 0 auto; border-radius: 50%; background: var(--ui-info); animation: connection-pulse 1.6s ease-in-out infinite; }
.connection-notice--warning .connection-notice__pulse { background: var(--ui-warning); }
.connection-notice--danger .connection-notice__pulse { background: var(--ui-danger); }
.connection-notice__content { min-width: 0; display: grid; gap: 2px; }
.connection-notice__content strong { font-size: var(--ui-text-sm); }
.connection-notice__content span { font-size: var(--ui-text-sm); color: var(--ui-text-muted); }
.fade-enter-active, .fade-leave-active { transition: opacity var(--ui-motion-normal) var(--ui-ease), transform var(--ui-motion-normal) var(--ui-ease); }
.fade-enter-from, .fade-leave-to { opacity: 0; transform: translate(-50%, -10px); }
@keyframes connection-pulse { 0%, 100% { opacity: 0.45; transform: scale(0.85); } 50% { opacity: 1; transform: scale(1.15); } }
@keyframes route-progress { 0% { transform: translateX(-115%); } 55% { transform: translateX(145%); } 100% { transform: translateX(300%); } }
@media (prefers-reduced-motion: reduce) { .connection-notice__pulse, .route-progress__bar { animation: none; } .route-progress__bar { width: 100%; opacity: .72; } }
@media (max-width: 720px) {
	.app-shell { padding-bottom: calc(var(--ui-mobile-nav-height) + env(safe-area-inset-bottom)); }
	.app-content { margin-top: 0; }
	.connection-notice { top: var(--ui-space-2); width: calc(100% - 16px); padding: var(--ui-space-3); border-radius: var(--ui-radius-md); }
}
</style>
