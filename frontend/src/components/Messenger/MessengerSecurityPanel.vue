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
							<button type="button" class="text-action" :aria-expanded="shownQrDevice === device.deviceUid" @click="toggleQr(device)"><i class="fas fa-qrcode"></i> QR</button>
							<button v-if="!device.verified" type="button" class="text-action" @click="openScanner(device)"><i class="fas fa-camera"></i> Сканировать QR</button>
							<button v-if="!device.verified" type="button" class="verify-action" :disabled="workingDevice === device.deviceUid" @click="verifyDevice(device)">Код совпал</button>
							<button v-else type="button" class="text-action danger" :disabled="workingDevice === device.deviceUid" @click="unverifyDevice(device)">Снять проверку</button>
						</div>
						<div v-if="shownQrDevice === device.deviceUid" class="security-device__qr">
							<div class="security-device__qr-image" v-html="qrSvg(device)"></div>
							<div><strong>Покажите этот QR собеседнику</strong><p>QR содержит только версию протокола и текущий safety number. Он генерируется локально и не отправляется QR-сервисам.</p></div>
						</div>
					</article>
				</div>
				<footer class="security-panel__footer"><i class="fas fa-circle-info"></i><span>Проверка хранится локально на этом устройстве. QR упрощает независимую сверку, но PubChat пока не использует key-transparency log.</span></footer>
			</div>
		</Transition>

		<div v-if="scanDevice" class="qr-scanner" role="dialog" aria-modal="true" aria-labelledby="qr-scanner-title" @click.self="closeScanner">
			<div class="qr-scanner__card">
				<header><div><strong id="qr-scanner-title">Сверить QR устройства {{ shortDevice(scanDevice.deviceUid) }}</strong><small>QR должен быть показан собеседником на его устройстве.</small></div><button type="button" class="icon-action" aria-label="Закрыть" @click="closeScanner"><i class="fas fa-times"></i></button></header>
				<div v-if="scannerSupported" class="qr-scanner__video-wrap"><video ref="scannerVideo" autoplay muted playsinline></video><span class="qr-scanner__frame" aria-hidden="true"></span></div>
				<div v-else class="security-panel__notice"><i class="fas fa-mobile-screen"></i><span>Этот браузер не поддерживает локальное распознавание QR. Отсканируйте QR камерой/другим устройством и вставьте полученную строку ниже.</span></div>
				<div v-if="scannerMessage" class="security-panel__notice" :class="scannerTone === 'success' ? 'security-panel__notice--success' : scannerTone === 'danger' ? 'security-panel__notice--danger' : 'security-panel__notice--warning'" role="status"><i :class="scannerTone === 'success' ? 'fas fa-shield-circle-check' : 'fas fa-triangle-exclamation'"></i><span>{{ scannerMessage }}</span></div>
				<label class="qr-scanner__fallback"><span>Строка из QR</span><input v-model="manualQrPayload" type="text" autocomplete="off" spellcheck="false" placeholder="pubchat-e2ee-v1:…" @keydown.enter.prevent="verifyScannedPayload(manualQrPayload)" /></label>
				<div class="qr-scanner__actions"><button type="button" class="text-action" @click="closeScanner">Отмена</button><button type="button" class="verify-action" :disabled="!manualQrPayload.trim() || workingDevice === scanDevice.deviceUid" @click="verifyScannedPayload(manualQrPayload)">Проверить</button></div>
			</div>
		</div>
	</section>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useStore } from 'vuex';
import MessengerService from '@/API/MessengerService';
import { acknowledgePeerDirectory, getPeerDeviceSecurity, safetyNumberPayload, unverifyPeerDevice, verifyPeerDevice } from '@/crypto/deviceVerification';
import { createVerificationQrSvg, matchesVerificationQrPayload } from '@/crypto/verificationQr';

const store = useStore();
const policy = ref(null);
const security = ref(null);
const expanded = ref(false);
const loading = ref(false);
const error = ref(false);
const workingDevice = ref('');
const copiedDevice = ref('');
const shownQrDevice = ref('');
const scanDevice = ref(null);
const scannerVideo = ref(null);
const scannerSupported = ref(false);
const scannerMessage = ref('');
const scannerTone = ref('warning');
const manualQrPayload = ref('');
let scannerStream = null;
let scannerFrame = 0;
let detector = null;
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
const qrSvg = (device) => createVerificationQrSvg(device.safetyNumber, { scale: 5, margin: 4 });
const toggleQr = (device) => { shownQrDevice.value = shownQrDevice.value === device.deviceUid ? '' : device.deviceUid; };

const stopScannerStream = () => {
	if (scannerFrame) window.cancelAnimationFrame(scannerFrame);
	scannerFrame = 0;
	scannerStream?.getTracks?.().forEach((track) => track.stop());
	scannerStream = null;
	detector = null;
};
const scanFrame = async () => {
	if (!scanDevice.value || !detector || !scannerVideo.value) return;
	try {
		if (scannerVideo.value.readyState >= 2) {
			const codes = await detector.detect(scannerVideo.value);
			const value = codes?.find((item) => item.rawValue)?.rawValue;
			if (value) {
				await verifyScannedPayload(value);
				if (!scanDevice.value || scannerTone.value === 'success') return;
			}
		}
	} catch (scanError) {
		console.warn('QR detector error', scanError);
	}
	scannerFrame = window.requestAnimationFrame(scanFrame);
};
const openScanner = async (device) => {
	closeScanner();
	scanDevice.value = device;
	manualQrPayload.value = '';
	scannerMessage.value = '';
	scannerTone.value = 'warning';
	scannerSupported.value = Boolean(window.BarcodeDetector && navigator.mediaDevices?.getUserMedia);
	if (!scannerSupported.value) return;
	try {
		const formats = await window.BarcodeDetector.getSupportedFormats?.();
		if (Array.isArray(formats) && !formats.includes('qr_code')) { scannerSupported.value = false; return; }
		detector = new window.BarcodeDetector({ formats: ['qr_code'] });
		scannerStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false });
		await nextTick();
		if (!scanDevice.value || !scannerVideo.value) { stopScannerStream(); return; }
		scannerVideo.value.srcObject = scannerStream;
		await scannerVideo.value.play().catch(() => null);
		scannerFrame = window.requestAnimationFrame(scanFrame);
	} catch (cameraError) {
		console.warn('Не удалось открыть QR scanner', cameraError);
		stopScannerStream();
		scannerSupported.value = false;
		scannerMessage.value = 'Камера недоступна. Используйте системную камеру и вставьте строку из QR вручную.';
		scannerTone.value = 'warning';
	}
};
const closeScanner = () => {
	stopScannerStream();
	scanDevice.value = null;
	manualQrPayload.value = '';
	scannerMessage.value = '';
};
const verifyScannedPayload = async (rawPayload) => {
	const device = scanDevice.value;
	if (!device) return;
	if (!matchesVerificationQrPayload(rawPayload, device.safetyNumber)) {
		scannerMessage.value = 'QR не совпадает с текущим safety number этого устройства. Проверка не сохранена.';
		scannerTone.value = 'danger';
		return;
	}
	workingDevice.value = device.deviceUid;
	try {
		security.value = await verifyPeerDevice({ ownAccountUid: ownAccountUid.value, peerAccountUid: peerAccountUid.value, deviceUid: device.deviceUid });
		scannerMessage.value = 'QR совпал. Устройство проверено локально.';
		scannerTone.value = 'success';
		stopScannerStream();
	} catch (verifyError) {
		console.warn('Не удалось сохранить QR-проверку устройства', verifyError);
		scannerMessage.value = 'Ключи изменились во время проверки. Обновите устройства и повторите сверку.';
		scannerTone.value = 'danger';
	} finally {
		workingDevice.value = '';
	}
};

const shortDevice = (value) => String(value || '').slice(0, 8);
const refresh = (event) => { if (!event.detail?.peerUid || String(event.detail.peerUid) === peerAccountUid.value) loadPolicyAndSecurity(); };
watch(peerAccountUid, () => { closeScanner(); shownQrDevice.value = ''; expanded.value = false; loadPolicyAndSecurity(); });
onMounted(() => { window.addEventListener('pubchat:conversation-encryption-changed', refresh); window.addEventListener('pubchat:conversation-encryption-refresh', refresh); loadPolicyAndSecurity(); });
onBeforeUnmount(() => { stopScannerStream(); window.removeEventListener('pubchat:conversation-encryption-changed', refresh); window.removeEventListener('pubchat:conversation-encryption-refresh', refresh); if (copyTimer) window.clearTimeout(copyTimer); });
</script>

<style scoped>
.security-panel{border-bottom:1px solid var(--ui-border);background:var(--ui-surface);color:var(--ui-text)}.security-panel__summary{width:100%;display:flex;align-items:center;gap:.6rem;min-height:44px;padding:.45rem .8rem;border:0;background:transparent;color:inherit;text-align:left;cursor:pointer}.security-panel__summary:hover{background:var(--ui-surface-muted)}.security-panel__icon{width:28px;height:28px;display:grid;place-items:center;border-radius:50%;background:var(--ui-surface-muted);color:var(--ui-primary)}.security-panel--verified .security-panel__icon{color:var(--ui-success)}.security-panel--changed .security-panel__icon{color:var(--ui-warning)}.security-panel__copy{display:grid;min-width:0;flex:1}.security-panel__copy strong{font-size:.76rem}.security-panel__copy small{color:var(--ui-text-muted);font-size:.64rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.security-panel__chevron{font-size:.65rem;color:var(--ui-text-muted);transition:transform .16s ease}.security-panel__chevron.open{transform:rotate(180deg)}.security-panel__details{display:grid;gap:.65rem;padding:.75rem .85rem;border-top:1px solid var(--ui-border);background:var(--ui-surface-muted)}.security-panel__intro{display:flex;gap:.65rem;align-items:flex-start}.security-panel__intro>div{flex:1}.security-panel__intro p,.security-device p,.security-panel__footer{margin:.15rem 0 0;color:var(--ui-text-muted);font-size:.68rem;line-height:1.4}.icon-action{width:30px;height:30px;border:1px solid var(--ui-border);border-radius:50%;background:var(--ui-surface);color:var(--ui-text-muted)}.security-panel__notice{display:flex;gap:.5rem;align-items:flex-start;padding:.55rem;border:1px solid var(--ui-border);border-radius:10px;font-size:.69rem}.security-panel__notice>div{display:grid;gap:.1rem;flex:1}.security-panel__notice--warning{border-color:color-mix(in srgb,var(--ui-warning) 40%,var(--ui-border))}.security-panel__notice--danger{border-color:color-mix(in srgb,var(--ui-danger) 40%,var(--ui-border))}.security-panel__notice--success{border-color:color-mix(in srgb,var(--ui-success) 40%,var(--ui-border))}.security-panel__devices{display:grid;gap:.55rem}.security-device{padding:.65rem;border:1px solid var(--ui-border);border-radius:11px;background:var(--ui-surface)}.security-device.verified{border-color:color-mix(in srgb,var(--ui-success) 35%,var(--ui-border))}.security-device.fresh{border-color:color-mix(in srgb,var(--ui-warning) 40%,var(--ui-border))}.security-device header{display:flex;justify-content:space-between;gap:.5rem}.security-device header>div{display:grid}.security-device header small{color:var(--ui-text-muted);font-size:.62rem}.security-device header strong{font-size:.75rem}.security-device code{display:block;margin-top:.35rem;padding:.45rem;border-radius:8px;background:var(--ui-surface-muted);font-size:.72rem;letter-spacing:.04em;overflow-wrap:anywhere}.security-device__actions{display:flex;gap:.4rem;flex-wrap:wrap;margin-top:.45rem}.text-action,.verify-action{min-height:28px;padding:0 .55rem;border:1px solid var(--ui-border);border-radius:999px;background:var(--ui-surface);color:var(--ui-text);font-size:.65rem;font-weight:700}.verify-action{border-color:color-mix(in srgb,var(--ui-success) 35%,var(--ui-border));color:var(--ui-success)}.danger{color:var(--ui-danger)}.security-device__qr{display:grid;grid-template-columns:auto 1fr;align-items:center;gap:.7rem;margin-top:.65rem;padding:.6rem;border:1px solid var(--ui-border);border-radius:10px;background:var(--ui-surface-muted)}.security-device__qr-image{width:148px;max-width:38vw;padding:.3rem;border-radius:8px;background:#fff;line-height:0}.security-device__qr-image :deep(svg){display:block;width:100%;height:auto}.security-device__qr strong{font-size:.72rem}.security-panel__footer{display:flex;gap:.4rem}.qr-scanner{position:fixed;inset:0;z-index:500;display:grid;place-items:center;padding:1rem;background:rgba(0,0,0,.62)}.qr-scanner__card{width:min(440px,100%);display:grid;gap:.7rem;padding:.85rem;border:1px solid var(--ui-border);border-radius:16px;background:var(--ui-surface);box-shadow:0 18px 55px rgba(0,0,0,.35)}.qr-scanner__card>header{display:flex;gap:.6rem;align-items:flex-start}.qr-scanner__card>header>div{display:grid;gap:.15rem;flex:1}.qr-scanner__card>header strong{font-size:.82rem}.qr-scanner__card>header small{color:var(--ui-text-muted);font-size:.68rem}.qr-scanner__video-wrap{position:relative;aspect-ratio:1;overflow:hidden;border-radius:12px;background:#050505}.qr-scanner__video-wrap video{width:100%;height:100%;object-fit:cover}.qr-scanner__frame{position:absolute;inset:16%;border:2px solid rgba(255,255,255,.9);border-radius:12px;box-shadow:0 0 0 999px rgba(0,0,0,.16)}.qr-scanner__fallback{display:grid;gap:.25rem;font-size:.66rem;font-weight:700}.qr-scanner__fallback input{width:100%;height:38px;padding:0 .65rem;border:1px solid var(--ui-border-strong);border-radius:8px;background:var(--ui-surface-soft);color:var(--ui-text);font-family:monospace;font-size:.68rem}.qr-scanner__actions{display:flex;justify-content:flex-end;gap:.45rem}.spinning{animation:security-spin .8s linear infinite}@keyframes security-spin{to{transform:rotate(360deg)}}.security-details-enter-active,.security-details-leave-active{transition:opacity .15s ease}.security-details-enter-from,.security-details-leave-to{opacity:0}@media(max-width:680px){.security-panel__summary{padding:.4rem .55rem}.security-panel__details{padding:.65rem}.security-panel__copy small{display:none}.security-device code{font-size:.64rem}.security-device__qr{grid-template-columns:1fr;text-align:center}.security-device__qr-image{width:170px;max-width:100%;margin:auto}.qr-scanner{padding:.55rem}.qr-scanner__card{max-height:calc(100dvh - 1.1rem);overflow:auto}}
</style>
