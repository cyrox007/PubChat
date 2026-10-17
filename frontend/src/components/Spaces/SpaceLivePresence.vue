<template>
	<section
		class="live-presence"
		:class="{ 'live-presence--offline': !isConnected }"
		:aria-label="presenceAriaLabel"
		:title="presenceAriaLabel"
		aria-live="polite"
	>
		<div class="live-presence__copy">
			<span class="live-presence__status">
				<span class="live-presence__label">
					<span class="live-presence__dot" aria-hidden="true"></span>
					<span class="live-presence__place">{{ spaceName }}</span>
				</span>
				<strong>{{ presenceTitle }}</strong>
			</span>
			<small v-if="typingLabel" class="live-presence__typing" role="status">
				<span class="live-presence__typing-dots" aria-hidden="true"><i></i><i></i><i></i></span>
				{{ typingLabel }}
			</small>
			<small v-else class="live-presence__detail">{{ presenceDetail }}</small>
		</div>

		<div v-if="visibleUsers.length" class="live-presence__people" :aria-label="`Сейчас в пространстве: ${users.length}`">
			<RouterLink
				v-for="user in visibleUsers"
				:key="user.uid || user.account_uid || user.persona_uid"
				class="live-presence__person"
				:to="{ name: 'UserProfile', params: { uid: user.uid || user.account_uid } }"
				:title="user.display_name || user.username || 'Участник'"
			>
				<img
					v-if="user.avatar"
					:src="resolveAvatar(user.avatar)"
					alt=""
					@error="handleAvatarImageError($event, user.display_name || user.username)"
				/>
				<span v-else>{{ avatarFallback(user.display_name || user.username) }}</span>
			</RouterLink>
			<span v-if="hiddenCount" class="live-presence__more">+{{ hiddenCount }}</span>
		</div>
	</section>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { RouterLink } from 'vue-router';
import { useStore } from 'vuex';
import { handleAvatarImageError, publicAssetUrl } from '@/utils/publicAssetUrl';

const store = useStore();
const users = computed(() => store.getters['chat/getConnectedUsers'] || []);
const messages = computed(() => store.getters['chat/getMessages'] || []);
const currentRoom = computed(() => store.getters['chat/getCurrentRoom'] || null);
const connectionState = computed(() => store.getters['chat/getConnectionState']);
const isConnected = computed(() => connectionState.value === 'connected');
const currentUserUid = computed(() => store.getters.getUser?.uid || '');
const socket = computed(() => store.state.chat?.socket || null);
const visibleUsers = computed(() => users.value.slice(0, 5));
const hiddenCount = computed(() => Math.max(0, users.value.length - visibleUsers.value.length));
const otherPeopleCount = computed(() => users.value.filter((user) => String(user.uid || user.account_uid || '') !== String(currentUserUid.value)).length);
const spaceName = computed(() => String(currentRoom.value?.name || 'Пространство').trim() || 'Пространство');
const typingUserUids = ref([]);
const typingTimers = new Map();
let localTypingTimer = null;
let lastTypingSentAt = 0;

const recentConversation = computed(() => {
	const threshold = Date.now() - (10 * 60 * 1000);
	return messages.value.some((message) => {
		const value = message.created_at || message.timestamp;
		return value && new Date(value).getTime() >= threshold;
	});
});

const typingUsers = computed(() => {
	const byUid = new Map(users.value.map((user) => [String(user.uid || user.account_uid || ''), user]));
	return typingUserUids.value.map((uid) => byUid.get(String(uid))).filter(Boolean);
});

const typingLabel = computed(() => {
	const names = typingUsers.value.map((user) => user.display_name || user.username || 'Участник');
	if (!names.length) return '';
	if (names.length === 1) return `${names[0]} печатает…`;
	if (names.length === 2) return `${names[0]} и ${names[1]} печатают…`;
	return `${names[0]} и ещё ${names.length - 1} печатают…`;
});

const presenceTitle = computed(() => {
	if (!isConnected.value) return '· подключаемся';
	if (!users.value.length) return '· пока тихо';
	if (!otherPeopleCount.value) return '· Вы здесь';
	return `· ${users.value.length} ${pluralize(users.value.length, ['человек', 'человека', 'человек'])} здесь`;
});

const presenceAriaLabel = computed(() => {
	if (!isConnected.value) return `Пространство ${spaceName.value}: восстанавливаем соединение`;
	if (!users.value.length) return `Пространство ${spaceName.value}: сейчас никого не видно`;
	if (!otherPeopleCount.value) return `Вы сейчас в пространстве ${spaceName.value}`;
	return `Вы сейчас в пространстве ${spaceName.value}. Здесь ${users.value.length} ${pluralize(users.value.length, ['человек', 'человека', 'человек'])}`;
});

const presenceDetail = computed(() => {
	if (!isConnected.value) return 'Список обновится после восстановления realtime-связи.';
	if (recentConversation.value && otherPeopleCount.value) return 'Разговор идёт прямо сейчас.';
	if (otherPeopleCount.value) return 'Можно присоединиться к разговору.';
	return 'Новые участники увидят тему после входа.';
});

const removeTypingUser = (uid) => {
	const normalized = String(uid || '');
	if (!normalized) return;
	const timer = typingTimers.get(normalized);
	if (timer) window.clearTimeout(timer);
	typingTimers.delete(normalized);
	typingUserUids.value = typingUserUids.value.filter((item) => String(item) !== normalized);
};

const clearRemoteTyping = () => {
	typingTimers.forEach((timer) => window.clearTimeout(timer));
	typingTimers.clear();
	typingUserUids.value = [];
};

const setTypingUser = (uid, active, expiresIn = 5) => {
	const normalized = String(uid || '');
	if (!normalized || normalized === String(currentUserUid.value || '')) return;
	removeTypingUser(normalized);
	if (!active) return;
	if (!typingUserUids.value.includes(normalized)) typingUserUids.value = [...typingUserUids.value, normalized];
	const ttlMs = Math.min(10000, Math.max(1000, Number(expiresIn || 5) * 1000));
	typingTimers.set(normalized, window.setTimeout(() => removeTypingUser(normalized), ttlMs));
};

const handleSocketMessage = (event) => {
	try {
		const data = JSON.parse(event.data);
		if (data.type === 'typing') {
			setTypingUser(data.user_uid, Boolean(data.active), data.expires_in);
			return;
		}
		if (data.type === 'message') removeTypingUser(data.sender?.uid || data.sender_uid);
	} catch (_) {
		// The canonical chat store owns malformed-frame handling.
	}
};

const sendTypingState = (active) => {
	const currentSocket = socket.value;
	if (!currentSocket || currentSocket.readyState !== WebSocket.OPEN || !isConnected.value) return false;
	try {
		currentSocket.send(JSON.stringify({ type: 'typing', active: Boolean(active) }));
		return true;
	} catch (_) {
		return false;
	}
};

const stopLocalTyping = (sendStop = true) => {
	if (localTypingTimer) window.clearTimeout(localTypingTimer);
	localTypingTimer = null;
	if (sendStop && lastTypingSentAt) sendTypingState(false);
	lastTypingSentAt = 0;
};

const isComposerInput = (target) => target instanceof HTMLInputElement && target.matches('.composer__bar input[type="text"]');

const handleComposerInput = (event) => {
	if (!isComposerInput(event.target)) return;
	const value = String(event.target.value || '').trim();
	if (!value || !isConnected.value) {
		stopLocalTyping();
		return;
	}
	const now = Date.now();
	if (!lastTypingSentAt || now - lastTypingSentAt >= 2000) {
		if (sendTypingState(true)) lastTypingSentAt = now;
	}
	if (localTypingTimer) window.clearTimeout(localTypingTimer);
	localTypingTimer = window.setTimeout(() => stopLocalTyping(), 3000);
};

const handleComposerKeydown = (event) => {
	if (isComposerInput(event.target) && event.key === 'Enter') stopLocalTyping();
};

const handleComposerBlur = (event) => {
	if (isComposerInput(event.target)) stopLocalTyping();
};

watch(socket, (nextSocket, previousSocket) => {
	previousSocket?.removeEventListener?.('message', handleSocketMessage);
	clearRemoteTyping();
	stopLocalTyping(false);
	nextSocket?.addEventListener?.('message', handleSocketMessage);
}, { immediate: true });

watch(isConnected, (connected) => {
	if (!connected) {
		clearRemoteTyping();
		stopLocalTyping(false);
	}
});

onMounted(() => {
	document.addEventListener('input', handleComposerInput, true);
	document.addEventListener('keydown', handleComposerKeydown, true);
	document.addEventListener('focusout', handleComposerBlur, true);
});

onBeforeUnmount(() => {
	document.removeEventListener('input', handleComposerInput, true);
	document.removeEventListener('keydown', handleComposerKeydown, true);
	document.removeEventListener('focusout', handleComposerBlur, true);
	socket.value?.removeEventListener?.('message', handleSocketMessage);
	stopLocalTyping();
	clearRemoteTyping();
});

const resolveAvatar = publicAssetUrl;
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
.live-presence{display:flex;align-items:center;justify-content:space-between;gap:var(--ui-space-2);min-height:48px;padding:.42rem clamp(var(--ui-space-3),2vw,var(--ui-space-5));border-top:1px solid var(--ui-border);background:color-mix(in srgb,var(--ui-success-soft) 32%,var(--ui-surface))}.live-presence__copy{min-width:0;display:flex;align-items:center;gap:.5rem;flex-wrap:wrap}.live-presence__status{display:inline-flex;align-items:center;gap:.35rem;min-width:0}.live-presence__label{display:inline-flex;align-items:center;gap:.32rem;min-width:0;color:var(--ui-success);font-size:var(--ui-text-xs);font-weight:800;letter-spacing:.01em;white-space:nowrap}.live-presence__place{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.live-presence__dot{width:.42rem;height:.42rem;flex:0 0 .42rem;border-radius:50%;background:currentColor;box-shadow:0 0 0 .16rem color-mix(in srgb,var(--ui-success) 12%,transparent)}.live-presence__copy strong{font-size:var(--ui-text-xs);white-space:nowrap}.live-presence__copy small{color:var(--ui-text-muted);font-size:.68rem;line-height:1.2}.live-presence__detail{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.live-presence__typing{display:inline-flex;align-items:center;gap:.3rem;color:var(--ui-primary)!important}.live-presence__typing-dots{display:inline-flex;align-items:center;gap:2px}.live-presence__typing-dots i{width:4px;height:4px;border-radius:50%;background:currentColor;animation:typing-dot 1s infinite ease-in-out}.live-presence__typing-dots i:nth-child(2){animation-delay:.15s}.live-presence__typing-dots i:nth-child(3){animation-delay:.3s}.live-presence__people{display:flex;align-items:center;flex:0 0 auto}.live-presence__person,.live-presence__more{width:1.8rem;height:1.8rem;display:grid;place-items:center;margin-left:-.32rem;border:2px solid var(--ui-surface);border-radius:50%;background:var(--ui-primary-soft);color:var(--ui-primary);font-size:.66rem;font-weight:800;text-decoration:none;overflow:hidden}.live-presence__person:first-child{margin-left:0}.live-presence__person img{width:100%;height:100%;object-fit:cover}.live-presence__person:hover,.live-presence__person:focus-visible{z-index:1;outline:2px solid color-mix(in srgb,var(--ui-primary) 45%,transparent);outline-offset:1px}.live-presence__more{background:var(--ui-surface-muted);color:var(--ui-text-muted)}.live-presence--offline{background:var(--ui-surface-soft)}.live-presence--offline .live-presence__label{color:var(--ui-text-muted)}
@keyframes typing-dot{0%,60%,100%{opacity:.35;transform:translateY(0)}30%{opacity:1;transform:translateY(-2px)}}
@media(max-width:760px){.live-presence__detail{display:none}}
@media(max-width:560px){.live-presence{min-height:42px;padding:.32rem var(--ui-space-3)}.live-presence__copy{gap:.3rem}.live-presence__label,.live-presence__copy strong{font-size:.7rem}.live-presence__person,.live-presence__more{width:1.65rem;height:1.65rem}.live-presence__people .live-presence__person:nth-child(n+4){display:none}}
</style>
