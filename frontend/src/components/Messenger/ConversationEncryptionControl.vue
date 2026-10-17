<template>
	<div v-if="visible" class="conversation-encryption" :class="`conversation-encryption--${policy?.effective_mode || 'loading'}`" role="group" aria-label="Режим защиты личного разговора">
		<div class="conversation-encryption__copy">
			<i :class="policy?.effective_mode === 'e2ee' ? 'fas fa-lock' : 'fas fa-lock-open'" aria-hidden="true"></i>
			<span>
				<strong>{{ title }}</strong>
				<small>{{ detail }}</small>
			</span>
		</div>
		<div v-if="policy?.can_change" class="conversation-encryption__actions">
			<button type="button" :class="{ active: policy.effective_mode === 'plaintext' }" :disabled="saving" @click="setMode('plaintext')">Обычный</button>
			<button type="button" :class="{ active: policy.effective_mode === 'e2ee' }" :disabled="saving" @click="setMode('e2ee')">E2EE</button>
		</div>
	</div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { useStore } from 'vuex';
import MessengerService from '@/API/MessengerService';

const route = useRoute();
const store = useStore();
const policy = ref(null);
const loading = ref(false);
const saving = ref(false);
let requestGeneration = 0;

const activeDialog = computed(() => store.getters['messenger/getActiveDialog']);
const visible = computed(() => route.name === 'messenger' && Boolean(activeDialog.value));
const title = computed(() => {
	if (!policy.value) return 'Проверяем защиту';
	if (policy.value.system_policy === 'disabled') return 'Сквозное шифрование отключено системой';
	if (policy.value.system_policy === 'required') return 'Сквозное шифрование обязательно';
	return policy.value.effective_mode === 'e2ee' ? 'Сквозное шифрование включено' : 'Обычный диалог';
});
const detail = computed(() => {
	if (!policy.value) return 'Загружаем режим разговора…';
	if (policy.value.effective_mode === 'e2ee') {
		return policy.value.crypto_ready
			? 'Текст и вложения отправляются только как зашифрованные данные.'
			: 'Для защищённой отправки второму участнику нужно зарегистрировать E2EE-устройство.';
	}
	return 'Сообщения доступны серверным функциям PubChat. Старые E2EE-сообщения остаются зашифрованными.';
});

const load = async () => {
	const peerUid = activeDialog.value;
	if (!visible.value || !peerUid) { policy.value = null; return; }
	const generation = ++requestGeneration;
	loading.value = true;
	try {
		const response = await MessengerService.getConversationEncryption(peerUid);
		if (generation === requestGeneration) policy.value = response.data?.encryption || null;
	} catch (error) {
		if (generation === requestGeneration) policy.value = null;
		console.warn('Не удалось загрузить режим шифрования разговора', error);
	} finally {
		if (generation === requestGeneration) loading.value = false;
	}
};

const setMode = async (mode) => {
	if (!activeDialog.value || !policy.value?.can_change || saving.value) return;
	saving.value = true;
	try {
		const response = await MessengerService.setConversationEncryption(activeDialog.value, mode);
		policy.value = response.data?.encryption || policy.value;
		window.dispatchEvent(new CustomEvent('pubchat:conversation-encryption-changed', {
			detail: { peerUid: activeDialog.value, encryption: policy.value },
		}));
	} catch (error) {
		console.error('Не удалось изменить режим шифрования разговора', error);
	} finally {
		saving.value = false;
	}
};

watch([visible, activeDialog], load, { immediate: true });
const refresh = (event) => {
	if (!event.detail?.peerUid || String(event.detail.peerUid) === String(activeDialog.value)) load();
};
window.addEventListener('pubchat:conversation-encryption-refresh', refresh);
onBeforeUnmount(() => window.removeEventListener('pubchat:conversation-encryption-refresh', refresh));
</script>

<style scoped>
.conversation-encryption{position:fixed;z-index:118;right:1rem;top:calc(var(--ui-mobile-topbar-height) + .65rem);display:flex;align-items:center;gap:.75rem;max-width:min(560px,calc(100vw - 2rem));padding:.55rem .7rem;border:1px solid var(--ui-border);border-radius:14px;background:color-mix(in srgb,var(--ui-surface-raised) 96%,transparent);box-shadow:var(--ui-shadow-md);backdrop-filter:blur(10px)}
.conversation-encryption__copy{display:flex;align-items:center;gap:.55rem;min-width:0}.conversation-encryption__copy>i{color:var(--ui-text-muted)}.conversation-encryption--e2ee .conversation-encryption__copy>i{color:var(--ui-success)}.conversation-encryption__copy span{display:grid;min-width:0}.conversation-encryption__copy strong{font-size:.78rem}.conversation-encryption__copy small{max-width:330px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--ui-text-muted);font-size:.68rem}.conversation-encryption__actions{display:flex;gap:.2rem;padding:.18rem;border-radius:999px;background:var(--ui-surface-muted)}.conversation-encryption__actions button{min-height:30px;padding:0 .65rem;border:0;border-radius:999px;background:transparent;color:var(--ui-text-muted);font-size:.72rem;font-weight:700;cursor:pointer}.conversation-encryption__actions button.active{background:var(--ui-surface);color:var(--ui-primary);box-shadow:var(--ui-shadow-sm)}
@media(min-width:901px){.conversation-encryption{top:4.75rem;right:1.25rem}}
@media(max-width:680px){.conversation-encryption{left:.55rem;right:.55rem;top:calc(var(--ui-mobile-topbar-height) + .45rem);max-width:none}.conversation-encryption__copy small{display:none}.conversation-encryption__actions{margin-left:auto}.conversation-encryption__actions button{padding:0 .5rem}}
</style>
