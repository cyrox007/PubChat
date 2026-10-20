import NotificationService from '@/API/NotificationService';

const isPushApiSupported = () => (
	typeof window !== 'undefined'
	&& 'Notification' in window
	&& 'serviceWorker' in navigator
	&& 'PushManager' in window
);

const urlBase64ToUint8Array = (value) => {
	const padding = '='.repeat((4 - (value.length % 4)) % 4);
	const base64 = (value + padding).replace(/-/g, '+').replace(/_/g, '/');
	const raw = window.atob(base64);
	return Uint8Array.from([...raw].map((char) => char.charCodeAt(0)));
};

const serializeSubscription = (subscription) => {
	const serialized = subscription.toJSON();
	return {
		endpoint: subscription.endpoint,
		keys: {
			p256dh: serialized.keys?.p256dh || '',
			auth: serialized.keys?.auth || '',
		},
	};
};

const currentRegistration = async ({ waitUntilReady = false } = {}) => {
	if (!isPushApiSupported()) return null;
	const existing = await navigator.serviceWorker.getRegistration('/');
	if (existing || !waitUntilReady) return existing;
	return navigator.serviceWorker.ready;
};

export const dropLocalWebPushSubscription = async () => {
	if (!isPushApiSupported()) return false;
	const registration = await currentRegistration();
	const subscription = registration ? await registration.pushManager.getSubscription() : null;
	if (!subscription) return false;
	try {
		return await subscription.unsubscribe();
	} catch {
		return false;
	}
};

export const webPushCapability = async () => {
	const supported = isPushApiSupported();
	if (!supported) {
		return {
			supported: false,
			serverEnabled: false,
			permission: typeof Notification === 'undefined' ? 'unsupported' : Notification.permission,
			registered: false,
		};
	}

	let config = { enabled: false, public_key: null };
	let registeredDevices = 0;
	try {
		const [configResponse, statusResponse] = await Promise.all([
			NotificationService.webPushConfig(),
			NotificationService.webPushStatus(),
		]);
		config = configResponse.data || config;
		registeredDevices = Number(statusResponse.data?.registered_devices) || 0;
	} catch {
		// Capability checks are informational. Auth/bootstrap errors are surfaced by
		// the ordinary application lifecycle and must not trigger permission prompts.
	}

	const registration = await currentRegistration();
	const localSubscription = registration ? await registration.pushManager.getSubscription() : null;
	return {
		supported: true,
		serverEnabled: Boolean(config.enabled && config.public_key),
		permission: Notification.permission,
		registered: Boolean(localSubscription),
		registeredDevices,
		publicKey: config.public_key || null,
	};
};

export const enableMessengerWebPush = async () => {
	if (!isPushApiSupported()) throw new Error('web_push_unsupported');

	const configResponse = await NotificationService.webPushConfig();
	const config = configResponse.data || {};
	if (!config.enabled || !config.public_key) throw new Error('web_push_server_disabled');

	// This function must only be called from a direct user action. We deliberately
	// never request notification permission during app bootstrap.
	const permission = Notification.permission === 'granted'
		? 'granted'
		: await Notification.requestPermission();
	if (permission !== 'granted') throw new Error(permission === 'denied' ? 'web_push_denied' : 'web_push_not_granted');

	const registration = await currentRegistration({ waitUntilReady: true });
	if (!registration) throw new Error('service_worker_unavailable');
	let subscription = await registration.pushManager.getSubscription();
	if (!subscription) {
		subscription = await registration.pushManager.subscribe({
			userVisibleOnly: true,
			applicationServerKey: urlBase64ToUint8Array(config.public_key),
		});
	}

	try {
		await NotificationService.registerWebPushSubscription(serializeSubscription(subscription));
		await NotificationService.updateMessagePreferences({ web_push_messenger: true, web_push_space: true });
	} catch (error) {
		// A just-created local subscription that the server did not accept must not
		// linger as a misleading enabled device.
		try { await subscription.unsubscribe(); } catch { /* best effort */ }
		throw error;
	}

	return webPushCapability();
};

export const disableMessengerWebPush = async ({ disableAccountPreference = true } = {}) => {
	if (!isPushApiSupported()) {
		if (disableAccountPreference) {
			await NotificationService.updateMessagePreferences({ web_push_messenger: false, web_push_space: false });
		}
		return;
	}

	const registration = await currentRegistration();
	const subscription = registration ? await registration.pushManager.getSubscription() : null;
	if (subscription) {
		try {
			await NotificationService.removeWebPushSubscription(subscription.endpoint);
		} finally {
			try { await subscription.unsubscribe(); } catch { /* browser cleanup is best effort */ }
		}
	}
	if (disableAccountPreference) {
		await NotificationService.updateMessagePreferences({ web_push_messenger: false, web_push_space: false });
	}
};

export const detachWebPushDeviceBeforeLogout = async () => {
	if (!isPushApiSupported()) return;
	const registration = await currentRegistration();
	const subscription = registration ? await registration.pushManager.getSubscription() : null;
	if (!subscription) return;
	try {
		await NotificationService.removeWebPushSubscription(subscription.endpoint);
	} catch {
		// Logout must not be blocked by external-notification cleanup. The local
		// subscription is removed anyway so a later Account cannot inherit it.
	} finally {
		try { await subscription.unsubscribe(); } catch { /* best effort */ }
	}
};

export { isPushApiSupported, urlBase64ToUint8Array };
