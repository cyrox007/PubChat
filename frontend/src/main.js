import { createApp } from 'vue';
import App from './App.vue';
import router from './router';
import store from './stores';
import CallOverlay from '@/components/Calls/CallOverlay.vue';
import ConversationEncryptionControl from '@/components/Messenger/ConversationEncryptionControl.vue';
import { registerPubChatServiceWorker } from '@/pwa/registerServiceWorker';

import "@/assets/main.css";
import "@/assets/layout-fixes.css";
import "@/assets/ui-utilities.css";
import "@/assets/messaging-ux.css";
import "@/assets/mobile-density.css";

const bootstrap = async () => {
	await store.dispatch('initializeUser');
	if (store.getters.isAuth) {
		try {
			const restored = await store.dispatch('restoreSessionAccess');
			if (restored) await store.dispatch('syncIdentity');
		} catch (error) {
			console.warn('Не удалось восстановить сессию до запуска интерфейса:', error);
		}
	}

	const app = createApp(App);
	app.use(store);
	app.use(router);
	await router.isReady();
	app.mount('#app');

	const callRoot = document.createElement('div');
	callRoot.id = 'pubchat-call-root';
	document.body.appendChild(callRoot);
	const callApp = createApp(CallOverlay);
	callApp.use(store);
	callApp.use(router);
	callApp.mount(callRoot);

	const encryptionRoot = document.createElement('div');
	encryptionRoot.id = 'pubchat-conversation-encryption-root';
	document.body.appendChild(encryptionRoot);
	const encryptionApp = createApp(ConversationEncryptionControl);
	encryptionApp.use(store);
	encryptionApp.use(router);
	encryptionApp.mount(encryptionRoot);

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
