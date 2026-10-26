import { createApp } from 'vue';
import App from './App.vue';
import router from './router';
import store from './stores';
import CallOverlay from '@/components/Calls/CallOverlay.vue';
import ConversationEncryptionControl from '@/components/Messenger/ConversationEncryptionControl.vue';
import MessengerSecurityPanel from '@/components/Messenger/MessengerSecurityPanel.vue';
import { registerPubChatServiceWorker } from '@/pwa/registerServiceWorker';
import { avatarFallbackDataUrl, publicAssetUrl } from '@/utils/publicAssetUrl';

import "@/assets/main.css";
import "@/assets/layout-fixes.css";
import "@/assets/ui-utilities.css";
import "@/assets/messaging-ux.css";
import "@/assets/mobile-density.css";
import "@/assets/messenger-security.css";
import "@/assets/composer-single-line.css";
import "@/assets/mobile-room-v2.css";
import "@/assets/message-density-depth-v3.css";

const avatarContainerSelector = [
	'[class*="avatar"]',
	'.live-presence__person',
	'.owner-mini__avatar',
	'.person-row',
	'.persona-trigger',
].join(',');

// Keep legacy icon compatibility without waiting for a third-party CDN
// before the application can paint. Dynamic stylesheets do not block parsing.
const loadOptionalIconStyles = () => {
    if (document.getElementById('pubchat-optional-icons')) return;
    const link = document.createElement('link');
    link.id = 'pubchat-optional-icons';
    link.rel = 'stylesheet';
    link.href = 'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css';
    document.head.appendChild(link);
};

const installPublicImageRecovery = () => {
	document.addEventListener('error', (event) => {
		const image = event.target;
		if (!(image instanceof HTMLImageElement)) return;

		const current = image.currentSrc || image.src || image.getAttribute('src') || '';
		const normalized = publicAssetUrl(current);
		if (normalized && normalized !== current && image.dataset.publicAssetRetry !== '1') {
			image.dataset.publicAssetRetry = '1';
			image.src = normalized;
			return;
		}

		if (!image.closest(avatarContainerSelector) || image.dataset.avatarFallbackApplied === '1') return;
		image.dataset.avatarFallbackApplied = '1';
		image.src = avatarFallbackDataUrl(image.alt || '?');
	}, true);
};

const bootstrap = async () => {
    loadOptionalIconStyles();
	installPublicImageRecovery();
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

	const securityRoot = document.createElement('div');
	securityRoot.id = 'pubchat-messenger-security-root';
	document.body.appendChild(securityRoot);
	const securityApp = createApp(MessengerSecurityPanel);
	securityApp.use(store);
	securityApp.use(router);
	securityApp.mount(securityRoot);

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
