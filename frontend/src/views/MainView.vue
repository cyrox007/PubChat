<template>
	<main class="space-shell">
		<LeftSidebar
			:class="{ active: isLeftSidebarActive }"
			:spaces="memberSpaces"
			:activeSpaceUid="currentRoom?.uid || null"
			@close="closeLeftSidebar"
			@switch-space="navigateToSpace"
			@discover="goToDiscovery"
		/>

		<section class="space-main">
			<header class="space-header">
				<button
					class="space-header__icon"
					type="button"
					aria-label="Открыть список пространств"
					@click="toggleLeftSidebar"
				>
					<i class="fas fa-layer-group" aria-hidden="true"></i>
				</button>

				<div class="space-header__title">
					<span class="space-header__eyebrow">Пространство</span>
					<div class="space-header__title-row">
						<h1>{{ currentRoom?.name || loadingTitle }}</h1>
						<span
							v-if="currentRoom?.uid && !accessGate"
							class="connection-chip"
							:class="`connection-chip--${connectionState}`"
							role="status"
						>
							<span class="connection-chip__dot" aria-hidden="true"></span>
							{{ connectionLabel }}
						</span>
					</div>
				</div>

				<button
					class="space-header__icon"
					type="button"
					aria-label="Открыть информацию о пространстве"
					:disabled="!currentRoom?.uid || Boolean(accessGate)"
					@click="toggleRightSidebar"
				>
					<i class="fas fa-circle-info" aria-hidden="true"></i>
				</button>
			</header>

			<div
				v-if="realtimeNotice && currentRoom?.uid && !accessGate"
				class="space-notice"
				:class="`space-notice--${realtimeNotice.type}`"
				role="status"
			>
				<i class="fas fa-circle-info" aria-hidden="true"></i>
				<span>{{ realtimeNotice.message }}</span>
			</div>

			<section v-if="isLoading" class="space-loading" role="status" aria-live="polite" aria-label="Открываем пространство">
				<div class="space-loading__line space-loading__line--title ui-skeleton" aria-hidden="true"></div>
				<div class="space-loading__line ui-skeleton" aria-hidden="true"></div>
				<div class="space-loading__line space-loading__line--short ui-skeleton" aria-hidden="true"></div>
				<div class="space-loading__messages" aria-hidden="true">
					<span class="space-loading__bubble ui-skeleton"></span>
					<span class="space-loading__bubble space-loading__bubble--right ui-skeleton"></span>
					<span class="space-loading__bubble space-loading__bubble--short ui-skeleton"></span>
				</div>
			</section>

			<section v-else-if="accessGate" class="access-gate">
				<div class="access-gate__icon" aria-hidden="true"><i :class="accessGate.icon"></i></div>
				<span class="space-header__eyebrow">{{ accessGate.eyebrow }}</span>
				<h2>{{ accessGate.title }}</h2>
				<p>{{ accessGate.message }}</p>
				<div class="access-gate__actions">
					<button
						v-if="accessGate.action === 'request'"
						type="button"
						class="ui-button"
						:disabled="joining"
						@click="requestMembership"
					>
						{{ joining ? 'Отправляем…' : 'Подать заявку' }}
					</button>
					<button type="button" class="ui-button ui-button--ghost" @click="goToDiscovery">К пространствам</button>
				</div>
			</section>

			<div v-else-if="currentRoom?.uid" class="conversation-area">
				<section id="chat-messages" class="message-stream" aria-label="Сообщения пространства">
					<div v-if="messages.length === 0" class="stream-empty">
						<div class="stream-empty__icon" aria-hidden="true"><i class="fas fa-mug-hot"></i></div>
						<strong>Здесь пока тихо</strong>
						<span>Можно начать разговор без формальностей.</span>
					</div>

					<Message
						v-for="msg in messages"
						:key="msg.uid || msg.frontId || msg.tempId"
						:message="msg"
						@reply="handleMessageReply"
					/>
				</section>

				<div v-if="!isRealtimeReady" class="composer-state" role="status">
					<span v-if="connectionState === 'restricted'">Отправка сообщений недоступна в этом пространстве.</span>
					<span v-else-if="connectionState === 'offline'">Нет сети. Разговор восстановится автоматически.</span>
					<span v-else>Восстанавливаем связь с пространством…</span>
				</div>

				<MessageComposer
					ref="messageComposer"
					@send-message="handleSendMessage"
					:isDisabled="isComposerDisabled"
				/>
			</div>

			<section v-else class="space-placeholder">
				<div class="space-placeholder__art" aria-hidden="true"><i class="fas fa-compass"></i></div>
				<h2>Пространство недоступно</h2>
				<p>Оно могло быть архивировано или ссылка больше не ведёт в активное место.</p>
				<button class="ui-button" type="button" @click="goToDiscovery">Открыть discovery</button>
			</section>
		</section>


		<RightSidebar
			v-if="currentRoom?.uid && !isLoading && !accessGate"
			:class="{ active: isRightSidebarActive }"
			:roomInfo="currentRoom"
			:users="connectedUsers"
			@close="closeRightSidebar"
			@membership-changed="refreshCurrentSpace"
			@moderator-changed="handleModeratorChange"
			@user-banned="handleRestrictUser"
		/>
	</main>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useStore } from 'vuex';
import { v4 as uuidv4 } from 'uuid';
import DOMPurify from 'dompurify';

import SpacesService from '@/API/SpacesService';
import LeftSidebar from '@/components/LeftSidebar/index.vue';
import RightSidebar from '@/components/RightSidebar/index.vue';
import Message from '@/components/Message/ChatMessage.vue';
import MessageComposer from '@/components/MessageComposer/index.vue';

const store = useStore();
const route = useRoute();
const router = useRouter();

const isLoading = ref(false);
const isLeftSidebarActive = ref(false);
const isRightSidebarActive = ref(false);
const memberSpaces = ref([]);
const accessGate = ref(null);
const joining = ref(false);
const messageComposer = ref(null);
let loadGeneration = 0;

const currentRoom = computed(() => store.getters['chat/getCurrentRoom']);
const messages = computed(() => store.getters['chat/getMessages']);
const connectedUsers = computed(() => store.getters['chat/getConnectedUsers']);
const connectionState = computed(() => store.getters['chat/getConnectionState']);
const realtimeNotice = computed(() => store.getters['chat/getRealtimeNotice']);
const isUserMuted = computed(() => store.getters['chat/isUserMuted']);
const isRealtimeReady = computed(() => connectionState.value === 'connected');
const isComposerDisabled = computed(() => isUserMuted.value || !isRealtimeReady.value);
const currentUser = computed(() => store.getters.getUser || {});
const loadingTitle = computed(() => isLoading.value ? 'Открываем пространство…' : 'Пространство');

const connectionLabel = computed(() => ({
	idle: 'Не подключено',
	connecting: 'Подключаемся',
	authenticating: 'Проверяем сессию',
	connected: 'В эфире',
	reconnecting: 'Восстанавливаем',
	offline: 'Офлайн',
	restricted: 'Доступ ограничен',
}[connectionState.value] || 'Подключение'));

const isActiveMember = (space) => (
	space?.viewer_membership?.status === 'active'
	|| space?.viewer_membership?.role === 'owner'
	|| space?.owner_uid === currentUser.value.uid
);

const buildGate = (space, errorType = null) => {
	if (errorType === 'space_private' || errorType === 'space_access_denied') {
		return {
			icon: 'fas fa-lock',
			eyebrow: 'Закрытое пространство',
			title: 'Доступ ограничен',
			message: 'Это место доступно только участникам. Вернитесь в discovery и выберите пространство, открытое для вас.',
			action: null,
		};
	}
	if (space?.viewer_membership?.status === 'pending') {
		return {
			icon: 'fas fa-hourglass-half',
			eyebrow: 'Заявка отправлена',
			title: 'Создатели пространства увидят ваш запрос',
			message: 'Разговор откроется после одобрения участия. Пока можно найти другие живые места в PubChat.',
			action: null,
		};
	}
	if (space?.join_policy === 'request') {
		return {
			icon: 'fas fa-hand',
			eyebrow: 'Вход по заявке',
			title: 'Сначала нужно присоединиться',
			message: 'У этого пространства есть вход по заявке. После одобрения откроются разговор и участники.',
			action: 'request',
		};
	}
	if (space?.join_policy === 'invite') {
		return {
			icon: 'fas fa-envelope-open-text',
			eyebrow: 'По приглашению',
			title: 'Нужно приглашение участника',
			message: 'Это пространство не принимает свободные заявки. Найдите другое место или дождитесь приглашения.',
			action: null,
		};
	}
	return null;
};

const loadMemberSpaces = async () => {
	try {
		const response = await SpacesService.list({ limit: 50 });
		memberSpaces.value = (response.data.spaces || []).filter((space) => isActiveMember(space));
	} catch (error) {
		console.error('Не удалось загрузить навигацию пространств:', error);
	}
};

const openRealtimeSpace = async (space) => {
	accessGate.value = null;
	if (currentRoom.value?.uid === space.uid && isRealtimeReady.value) {
		store.commit('chat/setCurrentRoom', space);
		return;
	}
	await store.dispatch('chat/switchRoom', { room: space, roomId: space.uid });
	isRightSidebarActive.value = window.innerWidth >= 1100;
};

const loadRouteSpace = async (spaceUid) => {
	const generation = ++loadGeneration;
	isLoading.value = true;
	accessGate.value = null;
	isLeftSidebarActive.value = false;

	try {
		let response = await SpacesService.get(spaceUid);
		if (generation !== loadGeneration) return;
		let space = response.data.space;

		if (!isActiveMember(space)) {
			if (space.join_policy === 'open') {
				response = await SpacesService.join(space.uid);
				if (generation !== loadGeneration) return;
				space = response.data.space;
			} else {
				await store.dispatch('chat/disconnectSocket');
				store.commit('chat/setCurrentRoom', space);
				accessGate.value = buildGate(space);
				return;
			}
		}

		await openRealtimeSpace(space);
		await loadMemberSpaces();
	} catch (error) {
		if (generation !== loadGeneration) return;
		await store.dispatch('chat/disconnectSocket');
		store.commit('chat/clearCurrentRoom');
		const errorType = error.response?.data?.detail?.error_type;
		if (['space_private', 'space_access_denied', 'space_membership_required'].includes(errorType)) {
			accessGate.value = buildGate(null, errorType);
		} else {
			console.error('Не удалось открыть пространство:', error);
		}
	} finally {
		if (generation === loadGeneration) isLoading.value = false;
	}
};

const requestMembership = async () => {
	if (!currentRoom.value?.uid || joining.value) return;
	joining.value = true;
	try {
		const response = await SpacesService.join(currentRoom.value.uid);
		const space = response.data.space;
		store.commit('chat/setCurrentRoom', space);
		accessGate.value = buildGate(space);
		if (isActiveMember(space)) await openRealtimeSpace(space);
	} catch (error) {
		console.error('Не удалось отправить заявку в пространство:', error);
	} finally {
		joining.value = false;
	}
};

const handleMessageReply = (message) => {
	messageComposer.value?.setReply(message);
	scrollToBottom();
};

const handleSendMessage = async (messageData) => {
	if (isComposerDisabled.value) return;
	const sanitizedContent = DOMPurify.sanitize(messageData.content || '');
	store.dispatch('chat/sendMessage', {
		frontId: uuidv4(),
		content: sanitizedContent,
		content_type: messageData.content_type,
		media_metadata: messageData.media_metadata,
		sender: {
			uid: currentUser.value.uid,
			name: currentUser.value.display_name || currentUser.value.username,
			avatar: currentUser.value.avatar,
		},
		reply_to_uid: messageData.reply_to_uid,
		status: 'sending',
	});
};

const refreshCurrentSpace = async () => {
	if (!currentRoom.value?.uid) return;
	const response = await SpacesService.get(currentRoom.value.uid);
	store.commit('chat/setCurrentRoom', response.data.space);
	await loadMemberSpaces();
};

const handleModeratorChange = async ({ userId, isModerator }) => {
	if (!currentRoom.value?.uid) return;
	try {
		await SpacesService.updateMemberRole(
			currentRoom.value.uid,
			userId,
			isModerator ? 'moderator' : 'member',
		);
		await refreshCurrentSpace();
	} catch (error) {
		console.error('Не удалось изменить роль в пространстве:', error);
	}
};

const handleRestrictUser = async (userId) => {
	try {
		await store.dispatch('chat/sendBanAction', {
			target_user_uid: userId,
			reason: 'Нарушение правил пространства',
		});
	} catch (error) {
		console.error('Не удалось ограничить доступ к пространству:', error);
	}
};

const navigateToSpace = (space) => {
	if (space?.uid && space.uid !== route.params.uid) {
		router.push({ name: 'space', params: { uid: space.uid } });
	}
	isLeftSidebarActive.value = false;
};

const goToDiscovery = () => router.push({ name: 'chats' });
const toggleLeftSidebar = () => {
	isLeftSidebarActive.value = !isLeftSidebarActive.value;
	if (isLeftSidebarActive.value) isRightSidebarActive.value = false;
};
const closeLeftSidebar = () => { isLeftSidebarActive.value = false; };
const toggleRightSidebar = () => {
	if (!currentRoom.value?.uid) return;
	isRightSidebarActive.value = !isRightSidebarActive.value;
	if (isRightSidebarActive.value && window.innerWidth < 1100) isLeftSidebarActive.value = false;
};
const closeRightSidebar = () => {
	isRightSidebarActive.value = false;
	if (route.name !== 'space') router.push({ name: 'space', params: { uid: route.params.uid } });
};

const scrollToBottom = async () => {
	await nextTick();
	const container = document.getElementById('chat-messages');
	if (container) container.scrollTop = container.scrollHeight;
};

watch(
	() => route.params.uid,
	(spaceUid) => {
		if (spaceUid) loadRouteSpace(String(spaceUid));
	},
	{ immediate: true },
);

watch(
	() => messages.value.length,
	() => scrollToBottom(),
);

onBeforeUnmount(() => {
	loadGeneration += 1;
	store.dispatch('chat/disconnectSocket');
});
</script>

<style scoped>
.space-shell { position: relative; height: calc(100dvh - 4.35rem); min-height: 32rem; display: flex; overflow: hidden; border: 1px solid var(--ui-border); border-radius: var(--ui-radius-xl); background: var(--ui-surface); box-shadow: var(--ui-shadow-sm); }
.space-main { min-width: 0; flex: 1; display: flex; flex-direction: column; background: var(--ui-bg); }
.space-header { min-height: 4.25rem; display: grid; grid-template-columns: 2.75rem minmax(0, 1fr) 2.75rem; align-items: center; gap: var(--ui-space-3); padding: var(--ui-space-2) var(--ui-space-4); border-bottom: 1px solid var(--ui-border); background: color-mix(in srgb, var(--ui-surface) 96%, transparent); }
.space-header__icon { width: 2.65rem; height: 2.65rem; display: grid; place-items: center; border: 1px solid var(--ui-border); border-radius: var(--ui-radius-md); background: var(--ui-surface); color: var(--ui-text-muted); cursor: pointer; }
.space-header__icon:hover:not(:disabled) { background: var(--ui-surface-muted); color: var(--ui-text); }
.space-header__icon:disabled { opacity: .4; cursor: default; }
.space-header__title { min-width: 0; }
.space-header__eyebrow { display: block; color: var(--ui-text-subtle); font-size: var(--ui-text-xs); font-weight: 700; text-transform: uppercase; letter-spacing: .06em; }
.space-header__title-row { min-width: 0; display: flex; align-items: center; gap: var(--ui-space-3); }
.space-header h1 { min-width: 0; overflow: hidden; margin: .1rem 0 0; text-overflow: ellipsis; white-space: nowrap; font-size: var(--ui-text-lg); }
.connection-chip { min-height: 1.75rem; display: inline-flex; align-items: center; gap: var(--ui-space-1); padding: 0 var(--ui-space-2); border-radius: var(--ui-radius-pill); background: var(--ui-surface-muted); color: var(--ui-text-muted); font-size: var(--ui-text-xs); font-weight: 700; white-space: nowrap; }
.connection-chip__dot { width: .45rem; height: .45rem; border-radius: 50%; background: currentColor; }
.connection-chip--connected { background: var(--ui-success-soft); color: var(--ui-success); }
.connection-chip--reconnecting, .connection-chip--connecting, .connection-chip--authenticating { background: var(--ui-info-soft); color: var(--ui-info); }
.connection-chip--offline { background: var(--ui-warning-soft); color: var(--ui-warning); }
.connection-chip--restricted { background: var(--ui-danger-soft); color: var(--ui-danger); }
.space-notice { display: flex; align-items: center; gap: var(--ui-space-2); padding: var(--ui-space-2) var(--ui-space-4); border-bottom: 1px solid var(--ui-border); background: var(--ui-info-soft); color: var(--ui-info); font-size: var(--ui-text-sm); }
.space-notice--warning { background: var(--ui-warning-soft); color: var(--ui-warning); }
.space-notice--error, .space-notice--restricted { background: var(--ui-danger-soft); color: var(--ui-danger); }
.space-loading { min-height: 0; flex: 1; display: flex; flex-direction: column; gap: var(--ui-space-3); padding: var(--ui-space-5) clamp(var(--ui-space-3), 3vw, var(--ui-space-6)); overflow: hidden; }
.space-loading__line { width: min(72%, 28rem); height: .8rem; border-radius: var(--ui-radius-pill); }
.space-loading__line--title { width: min(46%, 18rem); height: 1rem; }
.space-loading__line--short { width: min(34%, 13rem); }
.space-loading__messages { min-height: 0; flex: 1; display: flex; flex-direction: column; justify-content: center; gap: var(--ui-space-3); }
.space-loading__bubble { width: min(64%, 28rem); height: 3.2rem; border-radius: 1rem; }
.space-loading__bubble--right { align-self: flex-end; width: min(52%, 23rem); }
.space-loading__bubble--short { width: min(38%, 16rem); height: 2.6rem; }
.conversation-area { min-height: 0; flex: 1; display: flex; flex-direction: column; }
.message-stream { min-height: 0; flex: 1; overflow-y: auto; padding: var(--ui-space-4) clamp(var(--ui-space-3), 3vw, var(--ui-space-6)); scroll-behavior: smooth; }
.stream-empty { min-height: 100%; display: grid; place-items: center; align-content: center; gap: var(--ui-space-2); text-align: center; color: var(--ui-text-muted); }
.stream-empty__icon { width: 3.25rem; height: 3.25rem; display: grid; place-items: center; border-radius: 50%; background: var(--ui-primary-soft); color: var(--ui-primary); font-size: var(--ui-text-xl); }
.stream-empty strong { color: var(--ui-text); font-size: var(--ui-text-lg); }
.composer-state { padding: var(--ui-space-2) var(--ui-space-4); border-top: 1px solid var(--ui-border); background: var(--ui-surface-soft); color: var(--ui-text-muted); font-size: var(--ui-text-xs); text-align: center; }
.space-placeholder, .access-gate { flex: 1; display: grid; place-items: center; align-content: center; gap: var(--ui-space-3); padding: var(--ui-space-8); text-align: center; }
.space-placeholder__art, .access-gate__icon { width: 5rem; height: 5rem; display: grid; place-items: center; border-radius: 1.75rem; background: var(--ui-primary-soft); color: var(--ui-primary); font-size: 2rem; transform: rotate(-4deg); }
.space-placeholder h2, .access-gate h2 { margin: var(--ui-space-2) 0 0; font-size: var(--ui-text-xl); }
.space-placeholder p, .access-gate p { width: min(100%, 32rem); margin: 0; color: var(--ui-text-muted); line-height: 1.55; }
.access-gate__icon { background: var(--ui-warning-soft); color: var(--ui-warning); transform: rotate(4deg); }
.access-gate__actions { display: flex; flex-wrap: wrap; justify-content: center; gap: var(--ui-space-2); margin-top: var(--ui-space-2); }
.ui-button--ghost { border: 1px solid var(--ui-border); background: transparent; color: var(--ui-text-muted); }
@media (max-width: 991px) {
	.space-shell { height: calc(100dvh - 4.35rem); min-height: 0; border-radius: var(--ui-radius-lg); }
	.space-header { padding-inline: var(--ui-space-3); }
}
@media (max-width: 720px) {
	.space-shell {
		height: calc(100dvh - var(--ui-mobile-topbar-height) - var(--ui-mobile-nav-height) - env(safe-area-inset-bottom));
		min-height: 0;
	}
	.space-header {
		min-height: 3.35rem;
		grid-template-columns: 2.35rem minmax(0, 1fr) 2.35rem;
		gap: var(--ui-space-2);
		padding: .3rem var(--ui-space-3);
	}
	.space-header__icon { width: 2.25rem; height: 2.25rem; }
	.message-stream { padding-block: var(--ui-space-3); }
}
@media (max-width: 560px) {
	.space-shell { margin-inline: calc(var(--ui-space-3) * -1); border-right: 0; border-left: 0; border-radius: 0; }
	.space-header__eyebrow { display: none; }
	.space-header__title-row { gap: var(--ui-space-2); }
	.space-header h1 { font-size: var(--ui-text-md); }
	.connection-chip { max-width: 6.5rem; min-height: 1.5rem; overflow: hidden; text-overflow: ellipsis; }
	.message-stream { padding-inline: var(--ui-space-3); }
	.space-loading { padding: var(--ui-space-3); }
	.access-gate, .space-placeholder { padding-inline: var(--ui-space-4); }
}
</style>
