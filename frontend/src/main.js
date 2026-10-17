import { createApp } from 'vue';
import App from './App.vue';
import router from './router';
import store from './stores';
import CallOverlay from '@/components/Calls/CallOverlay.vue';
import { registerPubChatServiceWorker } from '@/pwa/registerServiceWorker';

import "@/assets/main.css";
import "@/assets/layout-fixes.css";
import "@/assets/ui-utilities.css";
import "@/assets/messaging-ux.css";
import "@/assets/mobile-density.css";

const bootstrap = async () => {
	// Protected routes (especially a direct /admin page load) must see the
	// restored identity before the router runs its first navigation guard.
	// App.vue still owns realtime/background-service startup; this only hydrates
	// the authentication/role state required to choose the correct route.
	await store.dispatch('initializeUser');
	if (store.getters.isAuth) {
		await store.dispatch('syncIdentity').catch(() => null);
	}

	const app = createApp(App);
	app.use(store);
	app.use(router);
	await router.isReady();
	app.mount('#app');

	// Calls are intentionally mounted outside route content. A call must survive
	// route transitions and an incoming call must be visible from any authenticated screen.
	const callRoot = document.createElement('div');
	callRoot.id = 'pubchat-call-root';
	document.body.appendChild(callRoot);
	const callApp = createApp(CallOverlay);
	callApp.use(store);
	callApp.use(router);
	callApp.mount(callRoot);

	window.addEventListener('pubchat:account-access-restricted', () => {
		if (router.currentRoute.value.name !== 'restricted-safety') {
			router.replace({ name: 'restricted-safety' }).catch(() => null);
		}
	});

	registerPubChatServiceWorker();
};

bootstrap().catch((error) => {
	console.error('PubChat bootstrap failed:', error);
	const root = document.getElementById('app');
	if (root) {
		root.innerHTML = '<main class="ui-surface" style="max-width:720px;margin:32px auto;padding:24px"><h1>Не удалось открыть PubChat</h1><p>Обновите страницу. Если проблема повторится, проверьте соединение.</p></main>';
	}
});
