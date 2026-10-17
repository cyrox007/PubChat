<template>
	<main class="device-settings container">
		<header class="device-settings__header">
			<div>
				<span class="device-settings__eyebrow">Безопасность аккаунта</span>
				<h1>Устройства и сеансы</h1>
				<p>Здесь показаны активные авторизации этого аккаунта. Завершение сеанса не удаляет E2EE-ключ устройства — криптографические устройства управляются отдельно.</p>
			</div>
			<button class="ui-button ui-button--secondary" type="button" :disabled="loading || working" @click="loadSessions">
				<i class="fas fa-rotate" :class="{ spinning: loading }" aria-hidden="true"></i> Обновить
			</button>
		</header>

		<div v-if="error" class="device-notice device-notice--danger" role="alert">
			<i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
			<span>{{ error }}</span>
		</div>

		<section class="device-summary ui-surface">
			<div><strong>{{ devices.length }}</strong><span>активных устройств / браузеров</span></div>
			<div><strong>{{ sessionCount }}</strong><span>активных сеансов</span></div>
			<button class="ui-button ui-button--danger" type="button" :disabled="loading || working || sessionCount <= 1" @click="revokeOthers">
				Выйти на всех других устройствах
			</button>
		</section>

		<div v-if="loading && !devices.length" class="device-loading" role="status">Загружаем активные сеансы…</div>
		<div v-else class="device-list">
			<article v-for="device in devices" :key="device.device_uid" class="device-card ui-surface" :class="{ 'device-card--current': device.current }">
				<header>
					<span class="device-card__icon"><i :class="deviceIcon(device.user_agent)" aria-hidden="true"></i></span>
					<div class="device-card__title">
						<div><strong>{{ device.device_label || 'Неизвестное устройство' }}</strong><span v-if="device.current" class="current-badge">Это устройство</span></div>
						<small>{{ browserLabel(device.user_agent) }}</small>
					</div>
					<button v-if="!device.current" class="text-action danger" type="button" :disabled="working === device.device_uid" @click="revokeDevice(device)">Завершить все сеансы</button>
				</header>

				<div class="session-list">
					<div v-for="session in device.sessions" :key="session.uid" class="session-row">
						<div>
							<strong>{{ session.current ? 'Текущий сеанс' : 'Сеанс' }}</strong>
							<small>Последняя активность: {{ formatDate(session.last_seen_at) }}</small>
							<small v-if="session.ip_address">IP: {{ session.ip_address }}</small>
						</div>
						<button class="text-action" :class="{ danger: !session.current }" type="button" :disabled="working === session.uid" @click="revokeSession(session)">
							{{ session.current ? 'Выйти здесь' : 'Завершить' }}
						</button>
					</div>
				</div>
			</article>
		</div>

		<div v-if="!loading && !devices.length && !error" class="device-empty ui-surface">
			<i class="fas fa-laptop" aria-hidden="true"></i>
			<strong>Активные сеансы не найдены</strong>
		</div>

		<footer class="device-footnote">
			<i class="fas fa-circle-info" aria-hidden="true"></i>
			<span>Одновременный вход с телефона, компьютера и нескольких вкладок разрешён. Один аккаунт остаётся одной личностью; presence считается online, пока активно хотя бы одно соединение.</span>
		</footer>
	</main>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useStore } from 'vuex';
import AuthService from '@/API/AuthService';

const router = useRouter();
const store = useStore();
const devices = ref([]);
const loading = ref(false);
const working = ref('');
const error = ref('');
const sessionCount = computed(() => devices.value.reduce((sum, device) => sum + (device.sessions?.length || 0), 0));

const formatDate = (value) => value ? new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : 'неизвестно';
const browserLabel = (ua) => {
	const value = String(ua || '');
	if (/Edg\//.test(value)) return 'Microsoft Edge';
	if (/Chrome\//.test(value) && !/Edg\//.test(value)) return 'Chrome';
	if (/Firefox\//.test(value)) return 'Firefox';
	if (/Safari\//.test(value) && !/Chrome\//.test(value)) return 'Safari';
	return 'Браузер / приложение PubChat';
};
const deviceIcon = (ua) => /Android|iPhone|Mobile/i.test(String(ua || '')) ? 'fas fa-mobile-screen-button' : 'fas fa-laptop';

const loadSessions = async () => {
	loading.value = true;
	error.value = '';
	try {
		const response = await AuthService.sessions();
		devices.value = response.data?.devices || [];
	} catch (loadError) {
		error.value = 'Не удалось получить список активных устройств. Обновите страницу и попробуйте снова.';
	} finally {
		loading.value = false;
	}
};

const finishCurrentSession = async () => {
	await store.dispatch('clearUser');
	await router.replace({ name: 'login', query: { reason: 'session' } });
};

const revokeSession = async (session) => {
	working.value = session.uid;
	error.value = '';
	try {
		const response = await AuthService.revokeSession(session.uid);
		if (response.data?.current_revoked) return finishCurrentSession();
		await loadSessions();
	} catch (actionError) {
		error.value = 'Не удалось завершить сеанс.';
	} finally {
		working.value = '';
	}
};

const revokeDevice = async (device) => {
	working.value = device.device_uid;
	error.value = '';
	try {
		const response = await AuthService.revokeDevice(device.device_uid);
		if (response.data?.current_revoked) return finishCurrentSession();
		await loadSessions();
	} catch (actionError) {
		error.value = 'Не удалось завершить сеансы устройства.';
	} finally {
		working.value = '';
	}
};

const revokeOthers = async () => {
	working.value = 'others';
	error.value = '';
	try {
		await AuthService.revokeOtherSessions();
		await loadSessions();
	} catch (actionError) {
		error.value = 'Не удалось завершить остальные сеансы.';
	} finally {
		working.value = '';
	}
};

onMounted(loadSessions);
</script>

<style scoped>
.device-settings{max-width:880px;padding-block:var(--ui-space-6) calc(var(--ui-space-8) + env(safe-area-inset-bottom));display:grid;gap:var(--ui-space-4)}.device-settings__header{display:flex;align-items:flex-start;justify-content:space-between;gap:var(--ui-space-4)}.device-settings__header h1{margin:.15rem 0;font-size:var(--ui-text-2xl)}.device-settings__header p{max-width:44rem;margin:0;color:var(--ui-text-muted);line-height:1.55}.device-settings__eyebrow{color:var(--ui-primary);font-size:var(--ui-text-xs);font-weight:800;text-transform:uppercase;letter-spacing:.06em}.device-summary{display:flex;align-items:center;gap:var(--ui-space-5);padding:var(--ui-space-4)}.device-summary>div{display:grid}.device-summary strong{font-size:var(--ui-text-xl)}.device-summary span{color:var(--ui-text-subtle);font-size:var(--ui-text-xs)}.device-summary button{margin-left:auto}.device-list{display:grid;gap:var(--ui-space-3)}.device-card{padding:var(--ui-space-4);border:1px solid var(--ui-border)}.device-card--current{border-color:color-mix(in srgb,var(--ui-primary) 38%,var(--ui-border))}.device-card>header{display:flex;align-items:center;gap:var(--ui-space-3)}.device-card__icon{width:2.65rem;height:2.65rem;display:grid;place-items:center;border-radius:var(--ui-radius-md);background:var(--ui-primary-soft);color:var(--ui-primary)}.device-card__title{min-width:0;flex:1;display:grid}.device-card__title>div{display:flex;align-items:center;gap:var(--ui-space-2);flex-wrap:wrap}.device-card__title small,.session-row small{color:var(--ui-text-subtle)}.current-badge{padding:.15rem .45rem;border-radius:var(--ui-radius-pill);background:var(--ui-success-soft);color:var(--ui-success);font-size:.65rem;font-weight:800}.session-list{margin-top:var(--ui-space-3);border-top:1px solid var(--ui-border)}.session-row{display:flex;align-items:center;gap:var(--ui-space-3);padding:var(--ui-space-3) 0;border-bottom:1px solid var(--ui-border)}.session-row:last-child{border-bottom:0}.session-row>div{flex:1;display:grid;gap:.12rem}.session-row strong{font-size:var(--ui-text-sm)}.session-row small{font-size:var(--ui-text-xs)}.text-action{min-height:2rem;padding:0 .7rem;border:1px solid var(--ui-border);border-radius:var(--ui-radius-pill);background:var(--ui-surface);color:var(--ui-text);font-weight:700}.text-action.danger{color:var(--ui-danger)}.device-notice,.device-footnote{display:flex;gap:var(--ui-space-2);padding:var(--ui-space-3);border-radius:var(--ui-radius-md);font-size:var(--ui-text-sm)}.device-notice--danger{background:var(--ui-danger-soft);color:var(--ui-danger)}.device-footnote{color:var(--ui-text-muted)}.device-loading,.device-empty{min-height:12rem;display:grid;place-items:center;align-content:center;gap:var(--ui-space-2);color:var(--ui-text-muted)}.device-empty i{font-size:2rem}.spinning{animation:device-spin .8s linear infinite}@keyframes device-spin{to{transform:rotate(360deg)}}@media(max-width:680px){.device-settings{padding-inline:var(--ui-space-3)}.device-settings__header{display:grid}.device-summary{display:grid;grid-template-columns:1fr 1fr}.device-summary button{grid-column:1/-1;margin-left:0}.device-card>header{align-items:flex-start;flex-wrap:wrap}.device-card>header>.text-action{width:100%}.session-row{align-items:flex-start}.session-row .text-action{flex:0 0 auto}}
</style>
