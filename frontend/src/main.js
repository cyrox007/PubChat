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

const app = createApp(App);
app.use(store);
app.use(router);
app.mount('#app');

// Calls are intentionally mounted outside route content. A call must survive route
// transitions and an incoming call must be visible from any authenticated screen.
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
