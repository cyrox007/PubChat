<template>
	<section class="live-presence" :class="{ 'live-presence--offline': !isConnected }" aria-live="polite">
		<div class="live-presence__copy">
			<span class="live-presence__label"><span class="live-presence__dot" aria-hidden="true"></span>Сейчас здесь</span>
			<strong>{{ presenceTitle }}</strong>
			<small>{{ presenceDetail }}</small>
		</div>

		<div v-if="visibleUsers.length" class="live-presence__people" :aria-label="`Сейчас в пространстве: ${users.length}`">
			<RouterLink
				v-for="user in visibleUsers"
				:key="user.uid || user.account_uid || user.persona_uid"
				class="live-presence__person"
				:to="{ name: 'UserProfile', params: { uid: user.uid || user.account_uid } }"
				:title="user.display_name || user.username || 'Участник'"
			>
				<img v-if="user.avatar" :src="resolveAvatar(user.avatar)" alt="" />
				<span v-else>{{ avatarFallback(user.display_name || user.username) }}</span>
			</RouterLink>
			<span v-if="hiddenCount" class="live-presence__more">+{{ hiddenCount }}</span>
		</div>
	</section>
</template>

<script setup>
import { computed } from 'vue';
import { RouterLink } from 'vue-router';

const props = defineProps({
	users: { type: Array, default: () => [] },
	messages: { type: Array, default: () => [] },
	isConnected: { type: Boolean, default: false },
	currentUserUid: { type: String, default: '' },
});

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '');
const visibleUsers = computed(() => props.users.slice(0, 5));
const hiddenCount = computed(() => Math.max(0, props.users.length - visibleUsers.value.length));
const otherPeopleCount = computed(() => props.users.filter((user) => String(user.uid || user.account_uid || '') !== String(props.currentUserUid || '')).length);
const recentConversation = computed(() => {
	const threshold = Date.now() - (10 * 60 * 1000);
	return props.messages.some((message) => {
		const value = message.created_at || message.timestamp;
		return value && new Date(value).getTime() >= threshold;
	});
});

const presenceTitle = computed(() => {
	if (!props.isConnected) return 'Уточняем, кто здесь';
	if (!props.users.length) return 'Пока никого не видно';
	if (!otherPeopleCount.value) return 'Вы здесь';
	return `${props.users.length} ${pluralize(props.users.length, ['человек', 'человека', 'человек'])} в пространстве`;
});

const presenceDetail = computed(() => {
	if (!props.isConnected) return 'Список обновится после восстановления realtime-связи.';
	if (recentConversation.value && otherPeopleCount.value) return 'Разговор идёт прямо сейчас.';
	if (otherPeopleCount.value) return 'Можно присоединиться к разговору без отдельного приглашения.';
	return 'Можно начать тему — новые участники увидят её, когда войдут.';
});

const resolveAvatar = (avatar) => /^https?:\/\//.test(avatar) ? avatar : `${apiBaseUrl}${avatar}`;
const avatarFallback = (value = '?') => String(value || '?').slice(0, 1).toUpperCase();
const pluralize = (value, forms) => {
	const n = Math.abs(Number(value)) % 100;
	const n1 = n % 10;
	if (n > 10 && n < 20) return forms[2];
	if (n1 > 1 && n1 < 5) return forms[1];
	if (n1 === 1) return forms[0];
	return forms[2];
};
</script>

<style scoped>
.live-presence{display:flex;align-items:center;justify-content:space-between;gap:var(--ui-space-3);padding:.7rem clamp(var(--ui-space-3),3vw,var(--ui-space-6));border-bottom:1px solid var(--ui-border);background:color-mix(in srgb,var(--ui-success-soft) 38%,var(--ui-surface));}.live-presence__copy{min-width:0;display:grid;gap:.05rem}.live-presence__label{display:inline-flex;align-items:center;gap:.4rem;color:var(--ui-success);font-size:var(--ui-text-xs);font-weight:800;text-transform:uppercase;letter-spacing:.04em}.live-presence__dot{width:.48rem;height:.48rem;border-radius:50%;background:currentColor;box-shadow:0 0 0 .2rem color-mix(in srgb,var(--ui-success) 14%,transparent)}.live-presence__copy strong{font-size:var(--ui-text-sm)}.live-presence__copy small{color:var(--ui-text-muted);font-size:var(--ui-text-xs)}.live-presence__people{display:flex;align-items:center;flex:0 0 auto}.live-presence__person,.live-presence__more{width:2rem;height:2rem;display:grid;place-items:center;margin-left:-.35rem;border:2px solid var(--ui-surface);border-radius:50%;background:var(--ui-primary-soft);color:var(--ui-primary);font-size:.72rem;font-weight:800;text-decoration:none;overflow:hidden}.live-presence__person:first-child{margin-left:0}.live-presence__person img{width:100%;height:100%;object-fit:cover}.live-presence__person:hover,.live-presence__person:focus-visible{z-index:1;outline:2px solid color-mix(in srgb,var(--ui-primary) 45%,transparent);outline-offset:1px}.live-presence__more{background:var(--ui-surface-muted);color:var(--ui-text-muted)}.live-presence--offline{background:var(--ui-surface-soft)}.live-presence--offline .live-presence__label{color:var(--ui-text-muted)}
@media(max-width:560px){.live-presence{padding:.55rem var(--ui-space-3)}.live-presence__copy small{display:none}.live-presence__person,.live-presence__more{width:1.8rem;height:1.8rem}.live-presence__people .live-presence__person:nth-child(n+4){display:none}.live-presence__people .live-presence__more{display:grid}}
</style>
