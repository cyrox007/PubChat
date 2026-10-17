<template>
	<section
		v-if="visible"
		class="conversation-encryption"
		:class="[
			`conversation-encryption--${policy?.effective_mode || 'loading'}`,
			{ 'conversation-encryption--blocked': sendBlocked || activationBlocked },
		]"
		aria-label="Режим защиты личного разговора"
	>
		<div class="conversation-encryption__summary">
			<button
				type="button"
				class="conversation-encryption__status"
				:aria-expanded="expanded"
				aria-controls="conversation-encryption-details"
				@click="expanded = !expanded"
			>
				<span class="conversation-encryption__icon" aria-hidden="true">
					<i :class="statusIcon"></i>
				</span>
				<span class="conversation-encryption__copy">
					<strong>{{ compactTitle }}</strong>
					<small>{{ sourceLabel }}</small>
				</span>
				<span v-if="sendBlocked || activationBlocked" class="conversation-encryption__warning-dot" title="Требуется внимание" aria-label="Требуется внимание"></span>
				<i class="fas fa-chevron-down conversation-encryption__chevron" :class="{ expanded }" aria-hidden="true"></i>
			</button>

			<div v-if="policy?.can_change" class="conversation-encryption__actions" aria-label="Выбор режима разговора">
				<button type="button" :class="{ active: policy.effective_mode === 'plaintext' }" :disabled="saving" @click="setMode('plaintext')">Обычный</button>
				<button
					type="button"
					:class="{ active: policy.effective_mode === 'e2ee' }"
					:disabled="saving || (policy.effective_mode !== 'e2ee' && !policy.can_enable_e2ee)"
					:title="e2eeButtonTitle"
					@click="setMode('e2ee')"
				>E2EE</button>
			</div>
		</div>

		<Transition name="encryption-details">
			<div v-if="expanded" id="conversation-encryption-details" class="conversation-encryption__details">
				<div class="conversation-encryption__headline">
					<strong>{{ title }}</strong>
					<span class="conversation-encryption__badge" :class="`conversation-encryption__badge--${policy?.effective_mode || 'loading'}`">{{ modeLabel }}</span>
				</div>
				<p>{{ detail }}</p>

				<div v-if="policy" class="conversation-encryption__facts">
					<span><i class="fas fa-shield-heart" aria-hidden="true"></i> Репутация: <b>{{ reputationLabel }}</b></span>
					<span v-if="policy.elevated_role"><i class="fas fa-user-shield" aria-hidden="true"></i> Роль: <b>{{ policy.elevated_role }}</b></span>
					<span><i class="fas fa-mobile-screen-button" aria-hidden="true"></i> Ваших E2EE-устройств: <b>{{ policy.own_crypto_devices }}</b></span>
					<span><i class="fas fa-user-shield" aria-hidden="true"></i> У собеседника: <b>{{ policy.peer_crypto_devices }}</b></span>
				</div>

				<div v-if="activationBlocked" class="conversation-encryption__blocked" role="status">
					<i class="fas fa-medal" aria-hidden="true"></i>
					<span><strong>E2EE — заработанная привилегия.</strong> Включить её можно с положительной репутацией «established»/«trusted» либо с ролью moderator/admin.</span>
				</div>

				<div v-if="sendBlocked" class="conversation-encryption__blocked" role="alert">
					<i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
					<span><strong>Отправка E2EE сейчас недоступна.</strong> {{ blockedReason }}</span>
				</div>

				<p class="conversation-encryption__history-note">
					<i class="fas fa-circle-info" aria-hidden="true"></i>
					Режим влияет только на новые сообщения. Уже включённый E2EE не понижается автоматически при изменении репутации: это исключает скрытый downgrade приватности.
				</p>
			</div>
		</Transition>
	</section>
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
const expanded = ref(false);
let requestGeneration = 0;

const activeDialog = computed(() => store.getters['messenger/getActiveDialog']);
const visible = computed(() => route.name === 'messenger' && Boolean(activeDialog.value));
const sendBlocked = computed(() => policy.value?.effective_mode === 'e2ee' && policy.value?.crypto_ready === false);
const activationBlocked = computed(() => policy.value?.system_policy === 'optional'
	&& policy.value?.effective_mode !== 'e2ee'
	&& policy.value?.can_change
	&& policy.value?.can_enable_e2ee === false);
const compactTitle = computed(() => {
	if (!policy.value) return 'Защита…';
	if (sendBlocked.value) return 'E2EE не готово';
	return policy.value.effective_mode === 'e2ee' ? 'E2EE' : 'Обычный';
});
const modeLabel = computed(() => policy.value?.effective_mode === 'e2ee' ? 'E2EE' : 'Обычный');
const reputationLabel = computed(() => ({
	unknown: 'не оценена',
	developing: 'формируется',
	established: 'положительная',
	trusted: 'высокая',
	concerning: 'требует внимания',
}[policy.value?.reputation_label] || policy.value?.reputation_label || 'не оценена'));
const statusIcon = computed(() => {
	if (!policy.value) return 'fas fa-spinner fa-spin';
	if (sendBlocked.value || activationBlocked.value) return 'fas fa-lock text-warning';
	return policy.value.effective_mode === 'e2ee' ? 'fas fa-lock' : 'fas fa-lock-open';
});
const sourceLabel = computed(() => {
	if (!policy.value) return 'проверяем режим';
	if (policy.value.system_policy === 'required') return 'обязательно системой';
	if (policy.value.system_policy === 'disabled') return 'отключено системой';
	if (policy.value.configured_mode) return 'выбрано для диалога';
	if (activationBlocked.value) return 'E2EE ещё не заработано';
	return 'обычный режим по умолчанию';
});
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
			? 'Текст и вложения новых сообщений отправляются как зашифрованные данные для устройств участников.'
			: 'Режим выбран, но безопасный канал нельзя создать, пока у обеих сторон нет активного E2EE-устройства.';
	}
	if (activationBlocked.value) return 'Обычный Messenger доступен. E2EE можно включить после получения положительной репутации или повышенной платформенной роли.';
	return 'Новые сообщения используют обычный Messenger transport. При желании E2EE можно включить вручную для этого разговора.';
});
const blockedReason = computed(() => {
	if (!policy.value) return '';
	if (Number(policy.value.own_crypto_devices || 0) < 1 && Number(policy.value.peer_crypto_devices || 0) < 1) return 'Нужно зарегистрировать E2EE-устройства обоим участникам.';
	if (Number(policy.value.own_crypto_devices || 0) < 1) return 'На этом аккаунте нет активного E2EE-устройства.';
	return 'У собеседника пока нет активного E2EE-устройства.';
});
const e2eeButtonTitle = computed(() => activationBlocked.value
	? 'Нужна положительная репутация established/trusted или роль moderator/admin'
	: 'Включить сквозное шифрование');

const publishState = () => {
	window.dispatchEvent(new CustomEvent('pubchat:conversation-encryption-state', {
		detail: { peerUid: activeDialog.value, encryption: policy.value, sendBlocked: sendBlocked.value, blockedReason: blockedReason.value },
	}));
};

const load = async () => {
	const peerUid = activeDialog.value;
	if (!visible.value || !peerUid) {
		policy.value = null;
		expanded.value = false;
		publishState();
		return;
	}
	const generation = ++requestGeneration;
	loading.value = true;
	try {
		const response = await MessengerService.getConversationEncryption(peerUid);
		if (generation === requestGeneration) {
			policy.value = response.data?.encryption || null;
			if (sendBlocked.value || activationBlocked.value) expanded.value = true;
			publishState();
		}
	} catch (error) {
		if (generation === requestGeneration) policy.value = null;
		console.warn('Не удалось загрузить режим шифрования разговора', error);
		publishState();
	} finally {
		if (generation === requestGeneration) loading.value = false;
	}
};

const setMode = async (mode) => {
	if (!activeDialog.value || !policy.value?.can_change || saving.value) return;
	if (mode === 'e2ee' && policy.value.effective_mode !== 'e2ee' && !policy.value.can_enable_e2ee) {
		expanded.value = true;
		return;
	}
	saving.value = true;
	try {
		const response = await MessengerService.setConversationEncryption(activeDialog.value, mode);
		policy.value = response.data?.encryption || policy.value;
		if (sendBlocked.value || activationBlocked.value) expanded.value = true;
		publishState();
		window.dispatchEvent(new CustomEvent('pubchat:conversation-encryption-changed', {
			detail: { peerUid: activeDialog.value, encryption: policy.value },
		}));
	} catch (error) {
		if (error.response?.data?.detail?.error_type === 'e2ee_privilege_required') expanded.value = true;
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
.conversation-encryption{position:fixed;z-index:118;right:1rem;top:calc(var(--ui-mobile-topbar-height) + .65rem);width:min(610px,calc(100vw - 2rem));border:1px solid var(--ui-border);border-radius:14px;background:color-mix(in srgb,var(--ui-surface-raised) 97%,transparent);box-shadow:var(--ui-shadow-md);backdrop-filter:blur(10px);overflow:hidden}.conversation-encryption--e2ee{border-color:color-mix(in srgb,var(--ui-success) 28%,var(--ui-border))}.conversation-encryption--blocked{border-color:color-mix(in srgb,var(--ui-warning) 45%,var(--ui-border))}.conversation-encryption__summary{display:flex;align-items:center;gap:.55rem;padding:.42rem .52rem}.conversation-encryption__status{display:flex;align-items:center;gap:.48rem;min-width:0;flex:1;padding:.14rem;border:0;background:transparent;color:var(--ui-text);text-align:left;cursor:pointer}.conversation-encryption__icon{width:28px;height:28px;display:grid;place-items:center;flex:0 0 auto;border-radius:50%;background:var(--ui-surface-muted);color:var(--ui-text-muted)}.conversation-encryption--e2ee .conversation-encryption__icon{background:color-mix(in srgb,var(--ui-success) 13%,var(--ui-surface));color:var(--ui-success)}.conversation-encryption--blocked .conversation-encryption__icon{background:color-mix(in srgb,var(--ui-warning) 14%,var(--ui-surface));color:var(--ui-warning)}.conversation-encryption__copy{display:grid;min-width:0;line-height:1.15}.conversation-encryption__copy strong{font-size:.76rem}.conversation-encryption__copy small{color:var(--ui-text-muted);font-size:.64rem}.conversation-encryption__warning-dot{width:7px;height:7px;flex:0 0 auto;border-radius:50%;background:var(--ui-warning)}.conversation-encryption__chevron{margin-left:auto;color:var(--ui-text-subtle);font-size:.65rem;transition:transform .16s ease}.conversation-encryption__chevron.expanded{transform:rotate(180deg)}.conversation-encryption__actions{display:flex;gap:.2rem;padding:.18rem;border-radius:999px;background:var(--ui-surface-muted)}.conversation-encryption__actions button{min-height:30px;padding:0 .65rem;border:0;border-radius:999px;background:transparent;color:var(--ui-text-muted);font-size:.7rem;font-weight:700;cursor:pointer}.conversation-encryption__actions button.active{background:var(--ui-surface);color:var(--ui-primary);box-shadow:var(--ui-shadow-sm)}.conversation-encryption__actions button:disabled{opacity:.5;cursor:not-allowed}.conversation-encryption__details{display:grid;gap:.52rem;padding:.72rem .8rem;border-top:1px solid var(--ui-border);background:var(--ui-surface)}.conversation-encryption__headline{display:flex;align-items:center;gap:.5rem}.conversation-encryption__headline strong{font-size:.8rem}.conversation-encryption__badge{margin-left:auto;padding:.18rem .45rem;border-radius:999px;background:var(--ui-surface-muted);color:var(--ui-text-muted);font-size:.62rem;font-weight:800}.conversation-encryption__badge--e2ee{background:color-mix(in srgb,var(--ui-success) 13%,var(--ui-surface));color:var(--ui-success)}.conversation-encryption__details p{margin:0;color:var(--ui-text-muted);font-size:.7rem;line-height:1.4}.conversation-encryption__facts{display:flex;flex-wrap:wrap;gap:.45rem .85rem;color:var(--ui-text-muted);font-size:.68rem}.conversation-encryption__facts span{display:inline-flex;align-items:center;gap:.3rem}.conversation-encryption__blocked{display:flex;align-items:flex-start;gap:.45rem;padding:.5rem .58rem;border:1px solid color-mix(in srgb,var(--ui-warning) 35%,var(--ui-border));border-radius:9px;background:color-mix(in srgb,var(--ui-warning) 8%,var(--ui-surface));color:var(--ui-text);font-size:.69rem;line-height:1.35}.conversation-encryption__blocked>i{margin-top:.12rem;color:var(--ui-warning)}.conversation-encryption__history-note{display:flex;gap:.35rem;align-items:flex-start}.conversation-encryption__history-note i{margin-top:.15rem}.encryption-details-enter-active,.encryption-details-leave-active{transition:opacity .15s ease,transform .15s ease}.encryption-details-enter-from,.encryption-details-leave-to{opacity:0;transform:translateY(-4px)}
@media(min-width:901px){.conversation-encryption{top:4.75rem;right:1.25rem}}
@media(max-width:680px){.conversation-encryption{left:.55rem;right:.55rem;top:calc(var(--ui-mobile-topbar-height) + .45rem);width:auto}.conversation-encryption__copy small{display:none}.conversation-encryption__actions{margin-left:auto}.conversation-encryption__actions button{padding:0 .48rem}.conversation-encryption__details{padding:.62rem}.conversation-encryption__facts{display:grid;gap:.3rem}}
@media(prefers-reduced-motion:reduce){.conversation-encryption__chevron,.encryption-details-enter-active,.encryption-details-leave-active{transition:none}}
</style>
