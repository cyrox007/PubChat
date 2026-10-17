<template>
	<section v-if="peerAccountUid" class="security-panel" :class="`security-panel--${tone}`">
		<button
			type="button"
			class="security-panel__summary"
			:aria-expanded="expanded"
			aria-controls="messenger-security-details"
			@click="expanded = !expanded"
		>
			<span class="security-panel__icon" aria-hidden="true"><i :class="summaryIcon"></i></span>
			<span class="security-panel__copy">
				<strong>{{ summaryTitle }}</strong>
				<small>{{ summaryDetail }}</small>
			</span>
			<span v-if="security?.devices?.length" class="security-panel__count">{{ security.devices.length }}</span>
			<i class="fas fa-chevron-down security-panel__chevron" :class="{ open: expanded }" aria-hidden="true"></i>
		</button>

		<Transition name="security-details">
			<div v-if="expanded" id="messenger-security-details" class="security-panel__details">
				<div class="security-panel__intro">
					<div>
						<strong>Проверка устройств</strong>
						<p>Сверьте код с собеседником другим способом — лично, голосом или видеозвонком. PubChat не может подтвердить этот код за вас.</p>
					</div>
					<button type="button" class="icon-action" :disabled="loading" aria-label="Обновить список устройств" @click="loadSecurity">
						<i class="fas fa-rotate" :class="{ spinning: loading }"></i>
					</button>
				</div>

				<div v-if="error" class="security-panel__notice security-panel__notice--danger" role="alert">
					<i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
					<span>Не удалось проверить криптографические устройства. Защищённые сообщения не считаются проверенными.</span>
				</div>

				<div v-else-if="security?.directoryChanged" class="security-panel__notice security-panel__notice--warning" role="status">
					<i class="fas fa-shield-halved" aria-hidden="true"></i>
					<div>
						<strong>Список устройств изменился</strong>
						<span v-if="security.added.length">Новых устройств: {{ security.added.length }}.</span>
						<span v-if="security.removed.length">Удалённых устройств: {{ security.removed.length }}.</span>
						<span v-if="security.changed.length">Изменивших ключ: {{ security.changed.length }}.</span>
					</div>
					<button type="button" class="text-action" :disabled="loading" @click="acknowledgeChanges">Я просмотрел</button>
				</div>

				<div v-if="loading && !security" class="security-panel__loading" role="status">
					<span class="security-panel__skeleton"></span>
					<span class="security-panel__skeleton short"></span>
				</div>

				<div v-else-if="security?.devices?.length" class="security-panel__devices">
					<article v-for="device in security.devices" :key="device.deviceUid" class="security-device" :class="{ 'security-device--verified': device.verified, 'security-device--new': device.isNew }">
						<header>
							<div>
								<span class="security-device__eyebrow">Устройство {{ shortDevice(device.deviceUid) }}</span>
								<strong>{{ device.verified ? 'Проверено' : device.isNew ? 'Новое устройство' : 'Не проверено' }}</strong>
							</div>
							<span class="security-device__state" :class="{ verified: device.verified }"><i :class="device.verified ? 'fas fa-shield-circle-check' : 'fas fa-shield'" aria-hidden="true"></i></span>
						</header>
						<p class="security-device__hint">Safety number для пары «это устройство ↔ устройство собеседника»</p>
						<code>{{ device.safetyNumber }}</code>
						<div class="security-device__actions">
							<button type="button" class="text-action" @click="copySafetyNumber(device)"><i class="far fa-copy" aria-hidden="true"></i>{{ copiedDevice === device.deviceUid ? 'Скопировано' : 'Скопировать' }}</button>
							<button v-if="!device.verified" type="button" class="verify-action" :disabled="workingDevice === device.deviceUid" @click="verifyDevice(device)"><i class="fas fa-check" aria-hidden="true"></i>Код совпал</button>
							<button v-else type="button" class="text-action danger" :disabled="workingDevice === device.deviceUid" @click="unverifyDevice(device)">Снять проверку</button>
						</div>
					</article>
				</div>

				<div v-else-if="!loading && !error" class="security-panel__empty">
					<i class="fas fa-lock-open" aria-hidden="true"></i>
					<div><strong>Нет криптографических устройств</strong><span>Текст этому собеседнику пока использует совместимый legacy-режим и не должен помечаться как E2EE.</span></div>
				</div>

				<footer class="security-panel__footer">
					<i class="fas fa-mobile-screen" aria-hidden="true"></i>
					<span>Проверка хранится локально для текущего устройства. На другом вашем устройстве коды нужно сверить отдельно.</span>
				</footer>
			</div>
		</Transition>
	</section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useStore } from 'vuex';
import {
	acknowledgePeerDirectory,
	getPeerDeviceSecurity,
	safetyNumberPayload,
	unverifyPeerDevice,
	verifyPeerDevice,
} from '@/crypto/deviceVerification';

const store = useStore();
const expanded = ref(false);
const loading = ref(false);
const error = ref(false);
const security = ref(null);
const workingDevice = ref('');
const copiedDevice = ref('');
let copyTimer = null;
let requestGeneration = 0;

const peerAccountUid = computed(() => String(store.getters['messenger/getActiveDialog'] || ''));
const ownAccountUid = computed(() => String(store.getters.getUser?.uid || ''));
const tone = computed(() => security.value?.status || (error.value ? 'changed' : 'loading'));

const summaryTitle = computed(() => {
	if (loading.value && !security.value) return 'Проверяем защиту';
	if (error.value) return 'Не удалось проверить устройства';
	switch (security.value?.status) {
		case 'verified': return 'Защищённый диалог проверен';
		case 'changed': return 'Устройства собеседника изменились';
		case 'unavailable': return 'E2EE пока недоступно';
		default: return 'Защищённый диалог не проверен';
	}
});

const summaryDetail = computed(() => {
	if (error.value) return 'Откройте сведения и повторите проверку';
	const count = security.value?.devices?.length || 0;
	if (!count) return 'Нет зарегистрированных E2EE-устройств';
	if (security.value?.status === 'changed') return 'Перед продолжением проверьте новые ключи';
	if (security.value?.status === 'verified') return `${count} ${pluralize(count, ['устройство', 'устройства', 'устройств'])} сверено`;
	const verified = security.value?.devices?.filter((item) => item.verified).length || 0;
	return verified ? `Проверено ${verified} из ${count}` : `${count} ${pluralize(count, ['устройство', 'устройства', 'устройств'])} без ручной проверки`;
});

const summaryIcon = computed(() => {
	if (error.value || security.value?.status === 'changed') return 'fas fa-triangle-exclamation';
	if (security.value?.status === 'verified') return 'fas fa-shield-circle-check';
	if (security.value?.status === 'unavailable') return 'fas fa-lock-open';
	return 'fas fa-shield-halved';
});

const loadSecurity = async () => {
	const peer = peerAccountUid.value;
	const own = ownAccountUid.value;
	if (!peer || !own) {
		security.value = null;
		return;
	}
	const generation = ++requestGeneration;
	loading.value = true;
	error.value = false;
	try {
		const result = await getPeerDeviceSecurity({ ownAccountUid: own, peerAccountUid: peer });
		if (generation === requestGeneration) security.value = result;
	} catch (loadError) {
		console.warn('Не удалось получить состояние E2EE устройств', loadError);
		if (generation === requestGeneration) error.value = true;
	} finally {
		if (generation === requestGeneration) loading.value = false;
	}
};

const verifyDevice = async (device) => {
	workingDevice.value = device.deviceUid;
	try {
		security.value = await verifyPeerDevice({ ownAccountUid: ownAccountUid.value, peerAccountUid: peerAccountUid.value, deviceUid: device.deviceUid });
		error.value = false;
	} catch (verifyError) {
		console.warn('Не удалось сохранить проверку устройства', verifyError);
		error.value = true;
	} finally {
		workingDevice.value = '';
	}
};

const unverifyDevice = async (device) => {
	workingDevice.value = device.deviceUid;
	try {
		security.value = await unverifyPeerDevice({ ownAccountUid: ownAccountUid.value, peerAccountUid: peerAccountUid.value, deviceUid: device.deviceUid });
	} catch (verifyError) {
		console.warn('Не удалось снять проверку устройства', verifyError);
	} finally {
		workingDevice.value = '';
	}
};

const acknowledgeChanges = async () => {
	loading.value = true;
	try {
		security.value = await acknowledgePeerDirectory({ ownAccountUid: ownAccountUid.value, peerAccountUid: peerAccountUid.value });
		error.value = false;
	} catch (ackError) {
		console.warn('Не удалось подтвердить список устройств', ackError);
		error.value = true;
	} finally {
		loading.value = false;
	}
};

const copySafetyNumber = async (device) => {
	const payload = safetyNumberPayload({
		ownAccountUid: ownAccountUid.value,
		peerAccountUid: peerAccountUid.value,
		ownDeviceUid: security.value?.ownDeviceUid,
		peerDeviceUid: device.deviceUid,
		safetyNumber: device.safetyNumber,
	});
	try {
		await navigator.clipboard.writeText(`${device.safetyNumber}\n${payload}`);
		copiedDevice.value = device.deviceUid;
		if (copyTimer) window.clearTimeout(copyTimer);
		copyTimer = window.setTimeout(() => { copiedDevice.value = ''; }, 1800);
	} catch (copyError) {
		console.warn('Не удалось скопировать safety number', copyError);
	}
};

const shortDevice = (value) => String(value || '').slice(0, 8);
const pluralize = (value, forms) => {
	const n = Math.abs(Number(value)) % 100;
	const n1 = n % 10;
	if (n > 10 && n < 20) return forms[2];
	if (n1 > 1 && n1 < 5) return forms[1];
	if (n1 === 1) return forms[0];
	return forms[2];
};

watch(peerAccountUid, () => {
	expanded.value = false;
	security.value = null;
	error.value = false;
	loadSecurity();
});

onMounted(loadSecurity);
</script>

<style scoped>
.security-panel{position:relative;border-top:1px solid var(--ui-border);background:var(--ui-surface);color:var(--ui-text);z-index:4}.security-panel__summary{width:100%;min-height:3.15rem;display:flex;align-items:center;gap:.65rem;padding:.55rem clamp(.75rem,3vw,1.25rem);border:0;background:transparent;color:inherit;text-align:left;cursor:pointer}.security-panel__summary:hover{background:var(--ui-surface-soft)}.security-panel__icon{width:2rem;height:2rem;display:grid;place-items:center;border-radius:50%;background:var(--ui-primary-soft);color:var(--ui-primary);flex:0 0 auto}.security-panel--verified .security-panel__icon{background:var(--ui-success-soft);color:var(--ui-success)}.security-panel--changed .security-panel__icon{background:var(--ui-warning-soft);color:var(--ui-warning)}.security-panel--unavailable .security-panel__icon{background:var(--ui-surface-muted);color:var(--ui-text-muted)}.security-panel__copy{display:grid;gap:.05rem;min-width:0;flex:1}.security-panel__copy strong{font-size:.82rem}.security-panel__copy small{font-size:.7rem;color:var(--ui-text-muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.security-panel__count{min-width:1.45rem;height:1.45rem;display:grid;place-items:center;padding:0 .3rem;border-radius:999px;background:var(--ui-surface-muted);color:var(--ui-text-muted);font-size:.68rem;font-weight:800}.security-panel__chevron{font-size:.7rem;color:var(--ui-text-subtle);transition:transform .18s ease}.security-panel__chevron.open{transform:rotate(180deg)}
.security-panel__details{display:grid;gap:.8rem;padding:.85rem clamp(.75rem,3vw,1.25rem) 1rem;border-top:1px solid var(--ui-border);background:var(--ui-surface-soft)}.security-panel__intro{display:flex;align-items:flex-start;justify-content:space-between;gap:.7rem}.security-panel__intro strong{font-size:.9rem}.security-panel__intro p{max-width:46rem;margin:.18rem 0 0;color:var(--ui-text-muted);font-size:.72rem;line-height:1.45}.icon-action{width:2rem;height:2rem;display:grid;place-items:center;border:1px solid var(--ui-border);border-radius:50%;background:var(--ui-surface);color:var(--ui-text-muted);cursor:pointer}.icon-action:disabled{opacity:.55;cursor:default}.spinning{animation:security-spin .8s linear infinite}
.security-panel__notice{display:flex;align-items:flex-start;gap:.55rem;padding:.65rem .7rem;border:1px solid var(--ui-border);border-radius:12px;font-size:.72rem}.security-panel__notice>i{margin-top:.15rem}.security-panel__notice>div{display:grid;gap:.1rem;flex:1}.security-panel__notice--warning{border-color:color-mix(in srgb,var(--ui-warning) 35%,var(--ui-border));background:var(--ui-warning-soft);color:var(--ui-warning-text,var(--ui-text))}.security-panel__notice--danger{border-color:color-mix(in srgb,var(--ui-danger) 35%,var(--ui-border));background:var(--ui-danger-soft);color:var(--ui-danger)}
.security-panel__devices{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,19rem),1fr));gap:.65rem}.security-device{display:grid;gap:.48rem;padding:.75rem;border:1px solid var(--ui-border);border-radius:14px;background:var(--ui-surface)}.security-device--verified{border-color:color-mix(in srgb,var(--ui-success) 34%,var(--ui-border))}.security-device--new{border-color:color-mix(in srgb,var(--ui-warning) 45%,var(--ui-border))}.security-device header{display:flex;align-items:flex-start;justify-content:space-between;gap:.6rem}.security-device header>div{display:grid;gap:.05rem}.security-device__eyebrow{font-size:.62rem;color:var(--ui-text-subtle);text-transform:uppercase;letter-spacing:.05em}.security-device header strong{font-size:.8rem}.security-device__state{color:var(--ui-text-subtle)}.security-device__state.verified{color:var(--ui-success)}.security-device__hint{margin:0;color:var(--ui-text-muted);font-size:.67rem}.security-device code{display:block;padding:.48rem .55rem;border-radius:9px;background:var(--ui-surface-muted);color:var(--ui-text);font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.72rem;line-height:1.5;letter-spacing:.03em;overflow-wrap:anywhere}.security-device__actions{display:flex;align-items:center;justify-content:flex-end;gap:.4rem;flex-wrap:wrap}.text-action,.verify-action{display:inline-flex;align-items:center;gap:.28rem;border:0;border-radius:8px;padding:.34rem .5rem;font-size:.68rem;font-weight:700;cursor:pointer}.text-action{background:transparent;color:var(--ui-primary)}.text-action.danger{color:var(--ui-danger)}.verify-action{background:var(--ui-primary);color:var(--ui-primary-contrast)}.text-action:disabled,.verify-action:disabled{opacity:.55;cursor:default}.security-panel__empty{display:flex;gap:.65rem;align-items:flex-start;padding:.7rem;border:1px dashed var(--ui-border-strong);border-radius:12px;color:var(--ui-text-muted)}.security-panel__empty>div{display:grid;gap:.08rem}.security-panel__empty strong{font-size:.78rem;color:var(--ui-text)}.security-panel__empty span{font-size:.7rem}.security-panel__footer{display:flex;align-items:flex-start;gap:.45rem;color:var(--ui-text-subtle);font-size:.65rem;line-height:1.4}.security-panel__loading{display:grid;gap:.35rem}.security-panel__skeleton{height:2.2rem;border-radius:10px;background:var(--ui-surface-muted);animation:security-pulse 1.2s ease-in-out infinite}.security-panel__skeleton.short{width:58%}.security-details-enter-active,.security-details-leave-active{transition:opacity .16s ease,transform .16s ease}.security-details-enter-from,.security-details-leave-to{opacity:0;transform:translateY(-4px)}
@keyframes security-spin{to{transform:rotate(360deg)}}@keyframes security-pulse{50%{opacity:.55}}
@media(max-width:560px){.security-panel__summary{min-height:2.8rem;padding:.45rem .7rem}.security-panel__icon{width:1.8rem;height:1.8rem}.security-panel__copy strong{font-size:.77rem}.security-panel__copy small{font-size:.65rem}.security-panel__details{padding:.7rem}.security-panel__devices{grid-template-columns:1fr}.security-device code{font-size:.68rem}.security-panel__intro p{font-size:.68rem}}
@media(prefers-reduced-motion:reduce){.security-panel__chevron,.security-details-enter-active,.security-details-leave-active{transition:none}.spinning,.security-panel__skeleton{animation:none}}
</style>
