<template>
	<section v-if="visible" class="security-panel" :class="`security-panel--${tone}`">
		<button type="button" class="security-panel__summary" :aria-expanded="expanded" @click="expanded = !expanded">
			<span class="security-panel__icon" aria-hidden="true"><i :class="summaryIcon"></i></span>
			<span class="security-panel__copy">
				<strong>{{ summaryTitle }}</strong>
				<small>{{ summaryDetail }}</small>
			</span>
			<i class="fas fa-chevron-down security-panel__chevron" :class="{ open: expanded }" aria-hidden="true"></i>
		</button>

		<Transition name="security-details">
			<div v-if="expanded" class="security-panel__details">
				<header class="security-panel__intro">
					<div>
						<strong>Проверка устройств E2EE</strong>
						<p>Сверьте safety number с собеседником по независимому доверенному каналу. Репутация даёт право включить E2EE, но сама по себе не подтверждает криптографическую личность устройства.</p>
					</div>
					<button class="icon-action" type="button" :disabled="loading" aria-label="Обновить устройства" @click="loadSecurity"><i class="fas fa-rotate" :class="{ spinning: loading }"></i></button>
				</header>

				<div v-if="error" class="security-panel__notice security-panel__notice--danger" role="alert">
					<i class="fas fa-triangle-exclamation"></i><span>Не удалось получить актуальные ключи устройств. Не считайте диалог вручную проверенным.</span>
				</div>

				<div v-else-if="security?.directoryChanged" class="security-panel__notice security-panel__notice--warning" role="alert">
					<i class="fas fa-shield-halved"></i>
					<div><strong>Требуется повторная проверка</strong><span>Новых: {{ security.added.length }}, удалённых: {{ security.removed.length }}, изменивших ключ: {{ security.changed.length }}.</span></div>
					<button type="button" class="text-action" :disabled="loading" @click="acknowledgeChanges">Я просмотрел</button>
				</div>

				<div v-if="loading && !security" class="security-panel__loading" role="status">Получаем ключи устройств…</div>
				<div v-else-if="security?.devices?.length" class="security-panel__devices">
					<article v-for="device in security.devices" :key="device.deviceUid" class="security-device" :class="{ verified: device.verified, fresh: device.isNew }">
						<header><div><small>Устройство {{ shortDevice(device.deviceUid) }}</small><strong>{{ device.verified ? 'Проверено вручную' : device.isNew ? 'Новое устройство' : 'Не проверено' }}</strong></div><i :class="device.verified ? 'fas fa-shield-circle-check' : 'fas fa-shield'"></i></header>
						<p>Safety number для текущего устройства и этого устройства собеседника:</p>
						<code>{{ device.safetyNumber }}</code>
						<div class="security-device__actions">
							<button type="button" class="text-action" @click="copySafetyNumber(device)"><i class="far fa-copy"></i> {{ copiedDevice === device.deviceUid ? 'Скопировано' : 'Скопировать' }}</button>
							<button v-if="!device.verified" type="button" class="verify-action" :disabled="workingDevice === device.deviceUid" @click="verifyDevice(device)">Код совпал</button>
							<button v-else type="button" class="text-action danger" :disabled="workingDevice === device.deviceUid" @click="unverifyDevice(device)">Снять проверку</button>
						</div>
					</article>
				</div>
				<footer class="security-panel__footer"><i class="fas fa-circle-info"></i><span>Проверка хранится локально на этом устройстве. PubChat пока не использует key-transparency log, поэтому safety number нужно сверять самостоятельно.</span></footer>
			</div>
		</Transition>
	</section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useStore } from 'vuex';
import MessengerService from '@/API/MessengerService';
import { acknowledgePeerDirectory, getPeerDeviceSecurity, safetyNumberPayload, unverifyPeerDevice, verifyPeerDevice } from '@/crypto/deviceVerification';

const store = useStore();
const policy = ref(null);
const security = ref(null);
const expanded = ref(false);
const loading = ref(false);
const error = ref(false);
const workingDevice = ref('');
const copiedDevice = ref('');
let requestGeneration = 0;
let copyTimer = null;

const peerAccountUid = computed(() => String(store.getters['messenger/getActiveDialog'] || ''));
const ownAccountUid = computed(() => String(store.getters.getUser?.uid || ''));
const visible = computed(() => Boolean(peerAccountUid.value && ownAccountUid.value && policy.value?.effective_mode === 'e2ee' && policy.value?.crypto_ready));
const tone = computed(() => error.value ? 'changed' : (security.value?.status || 'loading'));
const summaryTitle = computed(() => error.value ? 'Проверка устройств недоступна' : security.value?.status === 'verified' ? 'E2EE-устройства проверены' : security.value?.status === 'changed' ? 'Ключи устройств изменились' : 'Проверьте E2EE-устройства');
const summaryDetail = computed(() => {
	const count = security.value?.devices?.length || 0;
	if (security.value?.status === 'verified') return `${count} устройств сверено вручную`;
	if (security.value?.status === 'changed') return 'Перед доверием к новым ключам сверьте safety number';
	return count ? `${count} устройств требуют ручной проверки` : 'Safety number подтверждает ключи конкретных устройств';
});
const summaryIcon = computed(() => error.value || security.value?.status === 'changed' ? 'fas fa-triangle-exclamation' : security.value?.status === 'verified' ? 'fas fa-shield-circle-check' : 'fas fa-shield-halved');

const loadPolicyAndSecurity = async () => {
	const peer = peerAccountUid.value;
	const own = ownAccountUid.value;
	const generation = ++requestGeneration;
	security.value = null;
	error.value = false;
	if (!peer || !own) { policy.value = null; return; }
	try {
		const response = await MessengerService.getConversationEncryption(peer);
		if (generation !== requestGeneration) return;
		policy.value = response.data?.encryption || null;
		if (policy.value?.effective_mode !== 'e2ee' || !policy.value?.crypto_ready) return;
		await loadSecurity(generation);
	} catch (loadError) {
		console.warn('Не удалось загрузить состояние проверки E2EE', loadError);
		if (generation === requestGeneration) error.value = true;
	}
};

const loadSecurity = async (generation = requestGeneration) => {
	if (!visible.value) return;
	loading.value = true;
	try {
		const result = await getPeerDeviceSecurity({ ownAccountUid: ownAccountUid.value, peerAccountUid: peerAccountUid.value });
		if (generation === requestGeneration) { security.value = result; error.value = false; }
	} catch (loadError) {
		console.warn('Не удалось получить криптографические устройства', loadError);
		if (generation === requestGeneration) error.value = true;
	} finally {
		if (generation === requestGeneration) loading.value = false;
	}
};

const verifyDevice = async (device) => {
	workingDevice.value = device.deviceUid;
	try { security.value = await verifyPeerDevice({ ownAccountUid: ownAccountUid.value, peerAccountUid: peerAccountUid.value, deviceUid: device.deviceUid }); error.value = false; }
	catch (verifyError) { console.warn('Не удалось сохранить проверку устройства', verifyError); error.value = true; }
	finally { workingDevice.value = ''; }
};
const unverifyDevice = async (device) => {
	workingDevice.value = device.deviceUid;
	try { security.value = await unverifyPeerDevice({ ownAccountUid: ownAccountUid.value, peerAccountUid: peerAccountUid.value, deviceUid: device.deviceUid }); }
	catch (verifyError) { console.warn('Не удалось снять проверку устройства', verifyError); }
	finally { workingDevice.value = ''; }
};
const acknowledgeChanges = async () => {
	loading.value = true;
	try { security.value = await acknowledgePeerDirectory({ ownAccountUid: ownAccountUid.value, peerAccountUid: peerAccountUid.value }); error.value = false; }
	catch (ackError) { console.warn('Не удалось подтвердить новый каталог устройств', ackError); error.value = true; }
	finally { loading.value = false; }
};
const copySafetyNumber = async (device) => {
	const payload = safetyNumberPayload({ ownAccountUid: ownAccountUid.value, peerAccountUid: peerAccountUid.value, ownDeviceUid: security.value?.ownDeviceUid, peerDeviceUid: device.deviceUid, safetyNumber: device.safetyNumber });
	try {
		await navigator.clipboard.writeText(`${device.safetyNumber}\n${payload}`);
		copiedDevice.value = device.deviceUid;
		if (copyTimer) window.clearTimeout(copyTimer);
		copyTimer = window.setTimeout(() => { copiedDevice.value = ''; }, 1800);
	} catch (copyError) { console.warn('Не удалось скопировать safety number', copyError); }
};
const shortDevice = (value) => String(value || '').slice(0, 8);
const refresh = (event) => { if (!event.detail?.peerUid || String(event.detail.peerUid) === peerAccountUid.value) loadPolicyAndSecurity(); };
watch(peerAccountUid, () => { expanded.value = false; loadPolicyAndSecurity(); });
onMounted(() => { window.addEventListener('pubchat:conversation-encryption-changed', refresh); window.addEventListener('pubchat:conversation-encryption-refresh', refresh); loadPolicyAndSecurity(); });
onBeforeUnmount(() => { window.removeEventListener('pubchat:conversation-encryption-changed', refresh); window.removeEventListener('pubchat:conversation-encryption-refresh', refresh); if (copyTimer) window.clearTimeout(copyTimer); });
</script>

<style scoped>
.security-panel{border-bottom:1px solid var(--ui-border);background:var(--ui-surface);color:var(--ui-text)}.security-panel__summary{width:100%;display:flex;align-items:center;gap:.6rem;min-height:44px;padding:.45rem .8rem;border:0;background:transparent;color:inherit;text-align:left;cursor:pointer}.security-panel__summary:hover{background:var(--ui-surface-muted)}.security-panel__icon{width:28px;height:28px;display:grid;place-items:center;border-radius:50%;background:var(--ui-surface-muted);color:var(--ui-primary)}.security-panel--verified .security-panel__icon{color:var(--ui-success)}.security-panel--changed .security-panel__icon{color:var(--ui-warning)}.security-panel__copy{display:grid;min-width:0;flex:1}.security-panel__copy strong{font-size:.76rem}.security-panel__copy small{color:var(--ui-text-muted);font-size:.64rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.security-panel__chevron{font-size:.65rem;color:var(--ui-text-muted);transition:transform .16s ease}.security-panel__chevron.open{transform:rotate(180deg)}.security-panel__details{display:grid;gap:.65rem;padding:.75rem .85rem;border-top:1px solid var(--ui-border);background:var(--ui-surface-muted)}.security-panel__intro{display:flex;gap:.65rem;align-items:flex-start}.security-panel__intro>div{flex:1}.security-panel__intro p,.security-device p,.security-panel__footer{margin:.15rem 0 0;color:var(--ui-text-muted);font-size:.68rem;line-height:1.4}.icon-action{width:30px;height:30px;border:1px solid var(--ui-border);border-radius:50%;background:var(--ui-surface);color:var(--ui-text-muted)}.security-panel__notice{display:flex;gap:.5rem;align-items:flex-start;padding:.55rem;border:1px solid var(--ui-border);border-radius:10px;font-size:.69rem}.security-panel__notice>div{display:grid;gap:.1rem;flex:1}.security-panel__notice--warning{border-color:color-mix(in srgb,var(--ui-warning) 40%,var(--ui-border));}.security-panel__notice--danger{border-color:color-mix(in srgb,var(--ui-danger) 40%,var(--ui-border));}.security-panel__devices{display:grid;gap:.55rem}.security-device{padding:.65rem;border:1px solid var(--ui-border);border-radius:11px;background:var(--ui-surface)}.security-device.verified{border-color:color-mix(in srgb,var(--ui-success) 35%,var(--ui-border))}.security-device.fresh{border-color:color-mix(in srgb,var(--ui-warning) 40%,var(--ui-border))}.security-device header{display:flex;justify-content:space-between;gap:.5rem}.security-device header>div{display:grid}.security-device header small{color:var(--ui-text-muted);font-size:.62rem}.security-device header strong{font-size:.75rem}.security-device code{display:block;margin-top:.35rem;padding:.45rem;border-radius:8px;background:var(--ui-surface-muted);font-size:.72rem;letter-spacing:.04em;overflow-wrap:anywhere}.security-device__actions{display:flex;gap:.4rem;flex-wrap:wrap;margin-top:.45rem}.text-action,.verify-action{min-height:28px;padding:0 .55rem;border:1px solid var(--ui-border);border-radius:999px;background:var(--ui-surface);color:var(--ui-text);font-size:.65rem;font-weight:700}.verify-action{border-color:color-mix(in srgb,var(--ui-success) 35%,var(--ui-border));color:var(--ui-success)}.danger{color:var(--ui-danger)}.security-panel__footer{display:flex;gap:.4rem}.spinning{animation:security-spin .8s linear infinite}@keyframes security-spin{to{transform:rotate(360deg)}}.security-details-enter-active,.security-details-leave-active{transition:opacity .15s ease}.security-details-enter-from,.security-details-leave-to{opacity:0}@media(max-width:680px){.security-panel__summary{padding:.4rem .55rem}.security-panel__details{padding:.65rem}.security-panel__copy small{display:none}.security-device code{font-size:.64rem}}
</style>
