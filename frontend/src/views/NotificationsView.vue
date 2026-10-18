<template>
	<main class="notification-shell">
		<header class="notification-hero">
			<div>
				<span class="eyebrow">Личный inbox</span>
				<h1>Уведомления</h1>
				<p>PubChat сообщает о важном без давления: вы сами выбираете внешние напоминания, а сообщения пространств не преследуют вас, когда вы офлайн.</p>
			</div>
			<button v-if="unread" class="ui-button ui-button--ghost" type="button" :disabled="markingAll" @click="markAll">
				{{ markingAll ? 'Отмечаем…' : `Прочитать все · ${unread}` }}
			</button>
		</header>

		<section class="delivery-card" aria-labelledby="delivery-settings-title">
			<div class="delivery-card__intro">
				<div>
					<span class="eyebrow">Связь вне вкладки</span>
					<h2 id="delivery-settings-title">Как напоминать о личных сообщениях</h2>
					<p>Внешние уведомления относятся только к Messenger и включаются явно. Текст личной переписки в email и push не отправляется.</p>
				</div>
				<button class="ui-button ui-button--ghost" type="button" :disabled="deliveryLoading" @click="loadDeliverySettings">
					{{ deliveryLoading ? 'Проверяем…' : 'Обновить' }}
				</button>
			</div>

			<div v-if="deliveryError" class="delivery-error" role="alert">{{ deliveryError }}</div>

			<div class="delivery-options">
				<label class="delivery-option">
					<span class="delivery-option__icon"><i class="far fa-envelope" aria-hidden="true"></i></span>
					<span class="delivery-option__copy">
						<strong>Email, если давно не заходили</strong>
						<small>Одно аккуратное агрегированное напоминание после периода отсутствия и cooldown, а не письмо на каждое сообщение.</small>
					</span>
					<input
						type="checkbox"
						:checked="preferences.email_unread_dm_nudge"
						:disabled="deliveryLoading || savingEmail"
						@change="toggleEmailNudge"
					>
				</label>

				<div class="delivery-option delivery-option--push">
					<span class="delivery-option__icon"><i class="far fa-bell" aria-hidden="true"></i></span>
					<span class="delivery-option__copy">
						<strong>Push на этом устройстве</strong>
						<small>{{ pushDescription }}</small>
						<span v-if="pushState.registeredDevices > 0" class="device-count">Подключено устройств: {{ pushState.registeredDevices }}</span>
					</span>
					<button
						v-if="pushState.supported && pushState.serverEnabled && pushState.permission !== 'denied'"
						class="ui-button"
						type="button"
						:class="{ 'ui-button--ghost': pushState.registered }"
						:disabled="deliveryLoading || savingPush"
						@click="toggleWebPush"
					>
						{{ savingPush ? 'Сохраняем…' : (pushState.registered ? 'Отключить на устройстве' : 'Включить push') }}
					</button>
				</div>
			</div>

            <label class="delivery-option">
                <span class="delivery-option__icon"><i class="fas fa-cake-candles" aria-hidden="true"></i></span>
                <span class="delivery-option__copy">
                    <strong>Дни рождения друзей</strong>
                    <small>Напоминать во внутреннем центре PubChat только о днях рождения друзей, которые разрешили это в настройках. Год рождения не передаётся.</small>
                </span>
                <input type="checkbox" :checked="preferences.friend_birthday_reminders"
                    :disabled="deliveryLoading || savingBirthday" @change="toggleBirthdayReminders" />
            </label>
            <p class="delivery-note">Дни рождения пока доступны во внутреннем центре, без гарантированной доставки в фон. Для системного push необходим транспорт платформы. Разрешение браузера запрашивается только после нажатия «Включить push».</p>
		</section>

		<section v-if="loading" class="state-card" role="status">Синхронизируем напоминания…</section>
		<section v-else-if="errorMessage" class="state-card state-card--error" role="alert">
			<strong>Не удалось загрузить inbox</strong>
			<span>{{ errorMessage }}</span>
			<button class="ui-button" type="button" @click="load">Повторить</button>
		</section>
		<section v-else-if="items.length" class="notification-list" aria-label="Уведомления PubChat">
			<button
				v-for="item in items"
				:key="item.uid"
				type="button"
				class="notification-card"
				:class="{ unread: !item.is_read }"
				@click="openNotification(item)"
			>
				<span class="notification-icon"><i class="fas fa-bell" aria-hidden="true"></i></span>
				<span class="notification-copy">
					<span class="notification-title-row"><strong>{{ item.title }}</strong><span v-if="!item.is_read" class="unread-dot">Новое</span></span>
					<span class="notification-body">{{ item.body }}</span>
					<small>{{ contextLabel(item) }} · {{ formatDate(item.created_at) }}</small>
				</span>
				<i v-if="item.context_space_uid" class="fas fa-chevron-right notification-chevron" aria-hidden="true"></i>
			</button>
		</section>
		<section v-else class="state-card">
			<span class="empty-icon"><i class="far fa-bell" aria-hidden="true"></i></span>
			<strong>Здесь спокойно</strong>
			<span>Включите напоминание у нужной активности в «Жизни пространства». Ничего не включается без вашего выбора.</span>
			<RouterLink class="ui-button" to="/">Найти пространство</RouterLink>
		</section>
	</main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { RouterLink, useRouter } from 'vue-router';
import { useStore } from 'vuex';

import NotificationService from '@/API/NotificationService';
import {
	disableMessengerWebPush,
	enableMessengerWebPush,
	webPushCapability,
} from '@/pwa/webPush';

const router = useRouter();
const store = useStore();
const loading = ref(true);
const markingAll = ref(false);
const errorMessage = ref('');
const items = ref([]);
const unread = computed(() => store.getters['notifications/unread']);

const deliveryLoading = ref(false);
const deliveryError = ref('');
const savingEmail = ref(false);
const savingBirthday = ref(false);
const savingPush = ref(false);
const preferences = ref({
	email_unread_dm_nudge: false,
	friend_birthday_reminders: false,
	web_push_messenger: false,
});
const pushState = ref({
	supported: false,
	serverEnabled: false,
	permission: 'default',
	registered: false,
	registeredDevices: 0,
});

const pushDescription = computed(() => {
	if (!pushState.value.supported) return 'Этот браузер или режим сейчас не предоставляет Web Push. На iPhone/iPad проверьте установленную PWA.';
	if (!pushState.value.serverEnabled) return 'Сервер push пока не настроен. Остальные способы уведомлений продолжают работать.';
	if (pushState.value.permission === 'denied') return 'Уведомления запрещены в настройках браузера. Разрешение нужно изменить там вручную.';
	if (pushState.value.registered) return 'Это устройство подписано на приватные уведомления Messenger без текста сообщений.';
	return 'Получать системное уведомление о новом личном сообщении, когда PubChat не открыт.';
});

const loadDeliverySettings = async () => {
	deliveryLoading.value = true;
	deliveryError.value = '';
	try {
		const [preferenceResponse, capability] = await Promise.all([
			NotificationService.messagePreferences(),
			webPushCapability(),
		]);
		preferences.value = {
			...preferences.value,
			...(preferenceResponse.data?.preferences || {}),
		};
		pushState.value = { ...pushState.value, ...capability };
	} catch (error) {
		console.error('Не удалось загрузить настройки внешних уведомлений:', error);
		deliveryError.value = 'Не удалось проверить настройки уведомлений. Попробуйте ещё раз.';
	} finally {
		deliveryLoading.value = false;
	}
};

const toggleEmailNudge = async (event) => {
	const enabled = Boolean(event.target.checked);
	savingEmail.value = true;
	deliveryError.value = '';
	try {
		const response = await NotificationService.updateMessagePreferences({ email_unread_dm_nudge: enabled });
		preferences.value = { ...preferences.value, ...(response.data?.preferences || {}) };
	} catch (error) {
		event.target.checked = !enabled;
		deliveryError.value = 'Не удалось изменить email-напоминания.';
	} finally {
		savingEmail.value = false;
	}
};

const toggleBirthdayReminders = async (event) => {
    const enabled = Boolean(event.target.checked);
    savingBirthday.value = true;
    deliveryError.value = '';
    try {
        const response = await NotificationService.updateMessagePreferences({ friend_birthday_reminders: enabled });
        preferences.value = { ...preferences.value, ...(response.data?.preferences || {}) };
        if (enabled) await load();
    } catch {
        event.target.checked = !enabled;
        deliveryError.value = 'Не удалось изменить напоминания о днях рождения.';
    } finally {
        savingBirthday.value = false;
    }
};

const toggleWebPush = async () => {
	savingPush.value = true;
	deliveryError.value = '';
	try {
		if (pushState.value.registered) {
			await disableMessengerWebPush();
			preferences.value.web_push_messenger = false;
		} else {
			pushState.value = { ...pushState.value, ...(await enableMessengerWebPush()) };
			preferences.value.web_push_messenger = true;
		}
		pushState.value = { ...pushState.value, ...(await webPushCapability()) };
	} catch (error) {
		const code = error?.message || '';
		if (code === 'web_push_denied') {
			deliveryError.value = 'Браузер запретил уведомления. Разрешить их снова можно в настройках сайта.';
		} else if (code === 'web_push_server_disabled') {
			deliveryError.value = 'Web Push пока не настроен на сервере.';
		} else {
			deliveryError.value = 'Не удалось изменить push-подписку этого устройства.';
		}
		pushState.value = { ...pushState.value, ...(await webPushCapability()) };
	} finally {
		savingPush.value = false;
	}
};

const load = async () => {
	loading.value = true;
	errorMessage.value = '';
	try {
		await store.dispatch('notifications/sync');
		const response = await NotificationService.list({ limit: 100 });
		items.value = response.data.notifications || [];
		store.dispatch('notifications/setUnread', response.data.unread || 0);
	} catch (error) {
		console.error('Не удалось загрузить notifications:', error);
		errorMessage.value = 'Проверьте соединение и попробуйте ещё раз.';
	} finally {
		loading.value = false;
	}
};

const markAll = async () => {
	markingAll.value = true;
	try {
		await NotificationService.markAllRead();
		items.value = items.value.map((item) => ({ ...item, is_read: true }));
		store.dispatch('notifications/setUnread', 0);
	} catch {
		errorMessage.value = 'Не удалось обновить состояние уведомлений.';
	} finally {
		markingAll.value = false;
	}
};

const openNotification = async (item) => {
	if (!item.is_read) {
		try {
			const response = await NotificationService.markRead(item.uid);
			const index = items.value.findIndex((candidate) => candidate.uid === item.uid);
			if (index >= 0) items.value[index] = response.data.notification;
			store.dispatch('notifications/decrementUnread');
		} catch {
			// Navigation stays useful even if read-state update temporarily fails.
		}
	}
	if (item.context_space_uid) {
		await router.push({ name: 'space-life', params: { uid: item.context_space_uid } });
	}
};

const formatDate = (value) => value
	? new Intl.DateTimeFormat('ru', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
	: 'только что';
const contextLabel = (item) => item.occurrence_starts_at
	? `Встреча ${new Intl.DateTimeFormat('ru', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(item.occurrence_starts_at))}`
	: 'PubChat';

onMounted(() => {
	load();
	loadDeliverySettings();
});
</script>

<style scoped>
.notification-shell { display: grid; gap: var(--ui-space-5); padding-bottom: var(--ui-space-8); }.notification-hero { display: flex; align-items: flex-end; justify-content: space-between; gap: var(--ui-space-6); padding: clamp(1.4rem,4vw,2.4rem); border: 1px solid var(--ui-border); border-radius: var(--ui-radius-xl); background: linear-gradient(135deg,var(--ui-surface),var(--ui-primary-soft)); }.notification-hero > div { max-width: 44rem; }.eyebrow { color: var(--ui-primary); font-size: var(--ui-text-xs); font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }.notification-hero h1 { margin: .3rem 0 0; font-size: clamp(1.8rem,4vw,2.8rem); }.notification-hero p { margin: var(--ui-space-3) 0 0; color: var(--ui-text-muted); line-height: 1.6; }.delivery-card { display: grid; gap: var(--ui-space-4); padding: var(--ui-space-5); border: 1px solid var(--ui-border); border-radius: var(--ui-radius-xl); background: var(--ui-surface); box-shadow: var(--ui-shadow-sm); }.delivery-card__intro { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--ui-space-4); }.delivery-card h2 { margin: .25rem 0 0; font-size: var(--ui-text-xl); }.delivery-card__intro p { margin: var(--ui-space-2) 0 0; max-width: 46rem; color: var(--ui-text-muted); line-height: 1.55; }.delivery-options { display: grid; gap: var(--ui-space-2); }.delivery-option { display: grid; grid-template-columns: auto minmax(0,1fr) auto; align-items: center; gap: var(--ui-space-3); padding: var(--ui-space-3); border: 1px solid var(--ui-border); border-radius: var(--ui-radius-lg); background: var(--ui-surface-muted); }.delivery-option__icon { width: 2.5rem; height: 2.5rem; display: grid; place-items: center; border-radius: .8rem; background: var(--ui-primary-soft); color: var(--ui-primary); }.delivery-option__copy { min-width: 0; display: grid; gap: .2rem; }.delivery-option__copy small { color: var(--ui-text-muted); line-height: 1.4; }.device-count { color: var(--ui-text-subtle); font-size: var(--ui-text-xs); }.delivery-option input[type="checkbox"] { width: 1.2rem; height: 1.2rem; accent-color: var(--ui-primary); }.delivery-note { margin: 0; color: var(--ui-text-subtle); font-size: var(--ui-text-sm); line-height: 1.5; }.delivery-error { padding: var(--ui-space-3); border-radius: var(--ui-radius-md); background: color-mix(in srgb,var(--ui-danger) 10%,var(--ui-surface)); color: var(--ui-danger); }.notification-list { display: grid; gap: var(--ui-space-2); }.notification-card { width: 100%; display: grid; grid-template-columns: auto minmax(0,1fr) auto; align-items: center; gap: var(--ui-space-3); padding: var(--ui-space-4); border: 1px solid var(--ui-border); border-radius: var(--ui-radius-lg); background: var(--ui-surface); color: var(--ui-text); text-align: left; box-shadow: var(--ui-shadow-sm); cursor: pointer; }.notification-card.unread { border-color: color-mix(in srgb,var(--ui-primary) 28%,var(--ui-border)); background: color-mix(in srgb,var(--ui-primary-soft) 28%,var(--ui-surface)); }.notification-icon { width: 2.8rem; height: 2.8rem; display: grid; place-items: center; border-radius: .9rem; background: var(--ui-primary-soft); color: var(--ui-primary); }.notification-copy { min-width: 0; display: grid; gap: .25rem; }.notification-title-row { display: flex; align-items: center; gap: var(--ui-space-2); flex-wrap: wrap; }.notification-title-row strong { font-size: var(--ui-text-md); }.unread-dot { padding: .15rem .45rem; border-radius: var(--ui-radius-pill); background: var(--ui-primary); color: var(--ui-primary-contrast); font-size: .65rem; font-weight: 800; }.notification-body { color: var(--ui-text-muted); line-height: 1.5; }.notification-copy small { color: var(--ui-text-subtle); }.notification-chevron { color: var(--ui-text-subtle); }.state-card { min-height: 16rem; display: grid; place-items: center; align-content: center; gap: var(--ui-space-2); padding: var(--ui-space-6); border: 1px dashed var(--ui-border); border-radius: var(--ui-radius-xl); color: var(--ui-text-muted); text-align: center; }.state-card strong { color: var(--ui-text); font-size: var(--ui-text-lg); }.state-card span { max-width: 35rem; }.state-card .ui-button { margin-top: var(--ui-space-2); }.state-card--error { border-color: color-mix(in srgb,var(--ui-danger) 35%,var(--ui-border)); }.empty-icon { width: 3.5rem; height: 3.5rem; display: grid; place-items: center; border-radius: 1rem; background: var(--ui-surface-muted); color: var(--ui-text-subtle); font-size: 1.3rem; }
@media (max-width: 680px) { .notification-hero,.delivery-card__intro { align-items: stretch; flex-direction: column; }.notification-hero .ui-button,.delivery-card__intro .ui-button { width: 100%; }.delivery-option { grid-template-columns: auto 1fr; }.delivery-option > input,.delivery-option > button { grid-column: 1 / -1; width: 100%; }.notification-card { grid-template-columns: auto 1fr; }.notification-chevron { display: none; } }
</style>
