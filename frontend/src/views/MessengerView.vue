<template>
	<main class="dm-shell" :class="{ 'dm-shell--conversation-open': activeDialog }">
		<aside class="dm-list" aria-label="Личные разговоры">
			<header class="dm-list__header">
				<div>
					<span class="dm-eyebrow">Личные разговоры</span>
					<h1>Сообщения</h1>
				</div>
				<span class="connection-chip" :class="`connection-chip--${connectionState}`" role="status">
					<span class="connection-chip__dot" aria-hidden="true"></span>
					{{ connectionLabel }}
				</span>
			</header>

			<label class="dm-search">
				<i class="fas fa-magnifying-glass" aria-hidden="true"></i>
				<input v-model.trim="searchQuery" type="search" placeholder="Найти среди разговоров" :disabled="dialogsLoading" />
			</label>

			<div v-if="realtimeNotice" class="dm-inline-notice" :class="`dm-inline-notice--${realtimeNotice.type}`" role="status">
				<i class="fas fa-circle-info" aria-hidden="true"></i>
				<span>{{ realtimeNotice.message }}</span>
			</div>

			<div class="conversation-list" :aria-busy="dialogsLoading ? 'true' : 'false'">
				<Transition name="ui-state" mode="out-in">
					<div v-if="dialogsLoading" key="loading" class="conversation-skeleton" role="status" aria-live="polite">
						<span class="conversation-skeleton__label">Загружаем разговоры…</span>
						<div v-for="index in 5" :key="index" class="conversation-skeleton__row" aria-hidden="true">
							<span class="conversation-skeleton__avatar ui-skeleton"></span>
							<span class="conversation-skeleton__copy">
								<span class="conversation-skeleton__line conversation-skeleton__line--name ui-skeleton"></span>
								<span class="conversation-skeleton__line ui-skeleton"></span>
							</span>
						</div>
					</div>

					<div v-else-if="dialogsError" key="error" class="conversation-empty conversation-empty--error" role="alert">
						<div class="conversation-empty__icon" aria-hidden="true"><i class="fas fa-triangle-exclamation"></i></div>
						<strong>Не удалось загрузить разговоры</strong>
						<span>{{ dialogsError }}</span>
						<button class="ui-button ui-button--secondary" type="button" @click="hydrateDialogs">Повторить</button>
					</div>

					<div v-else key="content" class="conversation-list__content">
						<button
							v-for="dialog in filteredDialogs"
							:key="dialog.partner_id"
							type="button"
							class="conversation-card"
							:class="{ 'conversation-card--active': isActiveDialog(dialog.partner_id) }"
							@click="openConversation(dialog.partner_id)"
						>
							<span class="conversation-avatar">
								<img v-if="dialog.partner?.avatar" :src="resolveAvatar(dialog.partner.avatar)" alt="" />
								<span v-else>{{ avatarFallback(dialog.partner?.username) }}</span>
								<span class="presence-dot" :class="{ 'presence-dot--online': isOnline(dialog.partner_id) }" aria-hidden="true"></span>
							</span>
							<span class="conversation-copy">
								<strong>{{ dialog.partner?.display_name || dialog.partner?.username || 'Участник PubChat' }}</strong>
								<small>{{ dialog.last_message || 'Начните разговор' }}</small>
							</span>
							<span v-if="dialog.unread_count > 0" class="unread-badge" :aria-label="`${dialog.unread_count} непрочитанных`">
								{{ dialog.unread_count > 99 ? '99+' : dialog.unread_count }}
							</span>
						</button>

						<div v-if="!filteredDialogs.length" class="conversation-empty">
							<div class="conversation-empty__icon" aria-hidden="true"><i class="fas fa-message"></i></div>
							<strong>{{ searchQuery ? 'Ничего не найдено' : 'Здесь появятся ваши разговоры' }}</strong>
							<span v-if="!searchQuery">Личное общение в PubChat начинается из профиля или общего пространства.</span>
						</div>
					</div>
				</Transition>
			</div>
		</aside>

		<section class="dm-conversation">
			<template v-if="activeDialog">
				<header class="dm-conversation__header">
					<button class="back-button" type="button" aria-label="Назад к разговорам" @click="closeConversation">
						<i class="fas fa-arrow-left" aria-hidden="true"></i>
					</button>

					<RouterLink :to="`/profile/${activeDialog}`" class="active-persona">
						<span class="active-persona__avatar">
							<img v-if="activeDialogUser.avatar" :src="resolveAvatar(activeDialogUser.avatar)" alt="" />
							<span v-else>{{ avatarFallback(activeDialogUser.username) }}</span>
						</span>
						<span class="active-persona__copy">
							<strong>{{ activeDialogUser.display_name || activeDialogUser.username || 'Участник PubChat' }}</strong>
							<small>{{ isOnline(activeDialog) ? 'Сейчас в PubChat' : 'Не в сети' }}</small>
						</span>
					</RouterLink>
				</header>

				<div ref="messagesContainer" class="dm-stream" aria-label="История личного разговора" :aria-busy="conversationLoadingUid === activeDialog ? 'true' : 'false'">
					<div v-if="conversationLoadingUid === activeDialog" class="dm-stream__loading" role="status" aria-live="polite">
						<span>Загружаем историю…</span>
						<div class="message-skeleton message-skeleton--left ui-skeleton" aria-hidden="true"></div>
						<div class="message-skeleton message-skeleton--right ui-skeleton" aria-hidden="true"></div>
						<div class="message-skeleton message-skeleton--left message-skeleton--short ui-skeleton" aria-hidden="true"></div>
					</div>

					<div v-else-if="conversationError" class="dm-stream__empty dm-stream__empty--error" role="alert">
						<i class="fas fa-triangle-exclamation" aria-hidden="true"></i>
						<strong>Не удалось открыть разговор</strong>
						<span>{{ conversationError }}</span>
						<button class="ui-button ui-button--secondary" type="button" @click="openConversation(activeDialog)">Повторить</button>
					</div>

					<template v-else>
						<div v-if="getConversation(activeDialog).length === 0" class="dm-stream__empty">
							<i class="fas fa-mug-hot" aria-hidden="true"></i>
							<strong>Можно начать с простого «привет»</strong>
							<span>Личные сообщения подчиняются настройкам приватности каждого участника.</span>
						</div>

						<PrivateMessage
							v-for="message in getConversation(activeDialog)"
							:key="message.frontId || message.uid"
							:message="message"
							@retry="handleRetryMessage"
                            :ref="setObserverTarget"
						/>
					</template>
				</div>

				<div v-if="!isRealtimeReady" class="composer-state" role="status">
					<span v-if="connectionState === 'offline'">Нет сети. История останется на экране, связь восстановится автоматически.</span>
					<span v-else>Восстанавливаем личные сообщения…</span>
				</div>

				<MessageComposer
					ref="messageComposer"
					@send-message="handleSendMessage"
					:isDisabled="!isRealtimeReady"
				/>
			</template>

			<div v-else class="dm-placeholder">
				<div class="dm-placeholder__art" aria-hidden="true"><i class="fas fa-comment-dots"></i></div>
				<h2>Выберите разговор</h2>
				<p>Здесь нет ленты и случайных запросов: личный разговор начинается осознанно и с учётом настроек приватности.</p>
			</div>
		</section>
	</main>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { RouterLink } from 'vue-router';
import { useStore } from 'vuex';
import DOMPurify from 'dompurify';
import { v4 as uuidv4 } from 'uuid';

import MessengerService from '@/API/MessengerService';
import MessageComposer from '@/components/MessageComposer/index.vue';
import PrivateMessage from '@/components/Message/PrivateMessage.vue';

const store = useStore();
const searchQuery = ref('');
const messagesContainer = ref(null);
const observerTargets = ref([]);
const dialogs = ref([]);
const dialogsLoading = ref(true);
const dialogsError = ref('');
const conversationLoadingUid = ref(null);
const conversationError = ref('');
const messageComposer = ref(null);
let intersectionObserver = null;

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '');
const currentUser = computed(() => store.getters.getUser || {});
const activeDialog = computed(() => store.getters['messenger/getActiveDialog']);
const connectionState = computed(() => store.getters['messenger/getConnectionState']);
const realtimeNotice = computed(() => store.getters['messenger/getRealtimeNotice']);
const isRealtimeReady = computed(() => connectionState.value === 'connected');

const activeDialogUser = computed(() => {
	const dialog = dialogs.value.find((item) => item.partner_id === activeDialog.value);
	return dialog?.partner || {};
});

const filteredDialogs = computed(() => {
	const query = searchQuery.value.toLocaleLowerCase();
	if (!query) return dialogs.value;
	return dialogs.value.filter((dialog) => {
		const name = dialog.partner?.display_name || dialog.partner?.username || '';
		return name.toLocaleLowerCase().includes(query);
	});
});

const connectionLabel = computed(() => ({
	idle: 'Не подключено',
	connecting: 'Подключаемся',
	authenticating: 'Проверяем',
	connected: 'В эфире',
	reconnecting: 'Восстанавливаем',
	offline: 'Офлайн',
}[connectionState.value] || 'Подключение'));

const resolveAvatar = (avatar) => {
	if (!avatar) return '';
	if (/^https?:\/\//.test(avatar)) return avatar;
	return `${apiBaseUrl}${avatar}`;
};
const avatarFallback = (name = '?') => String(name || '?').slice(0, 1).toUpperCase();
const isOnline = (userId) => store.getters['messenger/isUserOnline'](userId);
const isActiveDialog = (userId) => activeDialog.value === userId;
const getConversation = (userId) => store.getters['messenger/getConversation'](userId);

const openConversation = async (userId) => {
	if (!userId) return;
	conversationLoadingUid.value = userId;
	conversationError.value = '';
	await store.dispatch('messenger/setActiveDialog', userId);
	try {
		await store.dispatch('messenger/requestConversation', {
			otherUserId: userId,
			requestId: uuidv4(),
		});
		await nextTick();
		setupIntersectionObserver();
	} catch (error) {
		console.error('Ошибка загрузки личного разговора:', error);
		conversationError.value = 'Проверьте соединение и попробуйте ещё раз.';
	} finally {
		if (conversationLoadingUid.value === userId) conversationLoadingUid.value = null;
	}
};

const closeConversation = () => {
	conversationLoadingUid.value = null;
	conversationError.value = '';
	store.dispatch('messenger/setActiveDialog', null);
};

const markMessageAsRead = (messageId) => store.dispatch('messenger/markMessageAsRead', messageId);

const setObserverTarget = (component) => {
	const element = component?.$el;
	if (element && !observerTargets.value.includes(element)) observerTargets.value.push(element);
};

const setupIntersectionObserver = () => {
	intersectionObserver?.disconnect();
	if (!messagesContainer.value) return;

	intersectionObserver = new IntersectionObserver((entries) => {
		entries.forEach((entry) => {
			if (!entry.isIntersecting) return;
			const messageId = entry.target.dataset.messageId;
			const isCurrentUserMessage = entry.target.dataset.isCurrentUser === 'true';
			const isAlreadyRead = entry.target.dataset.isRead === 'true';
			if (!isCurrentUserMessage && !isAlreadyRead && messageId) {
				markMessageAsRead(messageId);
				entry.target.dataset.isRead = 'true';
			}
		});
	}, { root: messagesContainer.value, threshold: 0.4 });

	observerTargets.value.forEach((target) => intersectionObserver.observe(target));
};

const handleRetryMessage = async (frontId) => {
    if (!activeDialog.value) return;
    try {
        await store.dispatch('messenger/retryPrivateMessage', { peerUid: activeDialog.value, frontId });
    } catch (error) {
        store.commit('messenger/SET_REALTIME_NOTICE', {
            type: 'warning', message: error.message || 'Не удалось повторить отправку.',
        });
    }
};

const handleSendMessage = async (messageData) => {
	if (!isRealtimeReady.value || !activeDialog.value) return;
	const rawContent = messageData.content || '';
	if (!rawContent.trim() && !messageData.media_metadata?.files?.length && !messageData.media_metadata?.voice) return;

	const sanitizedContent = DOMPurify.sanitize(rawContent);
	try {
        await store.dispatch('messenger/sendPrivateMessage', {
		frontId: uuidv4(),
		content: sanitizedContent,
		content_type: messageData.content_type,
		media_metadata: messageData.media_metadata,
		sender: {
			uid: currentUser.value.uid,
			name: currentUser.value.display_name || currentUser.value.username,
			avatar: currentUser.value.avatar,
		},
		receiver_uid: activeDialog.value,
		reply_to_uid: messageData.reply_to_uid,
		status: 'sending',
	    });
    } catch (error) {
        store.commit('messenger/SET_REALTIME_NOTICE', {
            type: 'warning', message: error.message || 'Сообщение не отправлено.',
        });
    }
	await nextTick();
	scrollToBottom();
};

const scrollToBottom = () => {
	if (messagesContainer.value) messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
};

const hydrateDialogs = async () => {
	dialogsLoading.value = true;
	dialogsError.value = '';
	try {
		const response = await MessengerService.getDialogs();
		if (response.data.status !== 'ok') throw new Error('unexpected_dialogs_response');
		dialogs.value = response.data.dialogs || [];
		const userIds = dialogs.value.map((dialog) => dialog.partner_id).filter(Boolean);
		if (userIds.length) store.dispatch('messenger/subscribeToStatuses', userIds);
	} catch (error) {
		console.error('Ошибка загрузки личных разговоров:', error);
		dialogsError.value = 'Проверьте соединение и повторите загрузку.';
	} finally {
		dialogsLoading.value = false;
	}
};

watch(
	() => getConversation(activeDialog.value)?.length,
	async () => {
		observerTargets.value = [];
		await nextTick();
		scrollToBottom();
		setupIntersectionObserver();
	},
);

onMounted(async () => {
	await hydrateDialogs();
	setupIntersectionObserver();
});

onBeforeUnmount(() => {
	intersectionObserver?.disconnect();
	const userIds = dialogs.value.map((dialog) => dialog.partner_id).filter(Boolean);
	if (userIds.length) store.dispatch('messenger/unsubscribeFromStatuses', userIds);
});
</script>

<style scoped>
.dm-shell {
	height: calc(100dvh - 4.35rem);
	min-height: 32rem;
	display: grid;
	grid-template-columns: minmax(17rem, 22rem) minmax(0, 1fr);
	overflow: hidden;
	border: 1px solid var(--ui-border);
	border-radius: var(--ui-radius-xl);
	background: var(--ui-surface);
	box-shadow: var(--ui-shadow-sm);
}

.dm-list { min-height: 0; display: flex; flex-direction: column; border-right: 1px solid var(--ui-border); background: var(--ui-surface); }
.dm-list__header { display: flex; align-items: flex-end; justify-content: space-between; gap: var(--ui-space-3); padding: var(--ui-space-4); }
.dm-eyebrow { display: block; margin-bottom: 0.15rem; color: var(--ui-text-subtle); font-size: var(--ui-text-xs); font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; }
.dm-list h1 { margin: 0; font-size: var(--ui-text-xl); }

.connection-chip { min-height: 1.75rem; display: inline-flex; align-items: center; gap: var(--ui-space-1); padding: 0 var(--ui-space-2); border-radius: var(--ui-radius-pill); background: var(--ui-surface-muted); color: var(--ui-text-muted); font-size: var(--ui-text-xs); font-weight: 700; white-space: nowrap; }
.connection-chip__dot { width: 0.45rem; height: 0.45rem; border-radius: 50%; background: currentColor; }
.connection-chip--connected { background: var(--ui-success-soft); color: var(--ui-success); }
.connection-chip--connecting, .connection-chip--authenticating, .connection-chip--reconnecting { background: var(--ui-info-soft); color: var(--ui-info); }
.connection-chip--offline { background: var(--ui-warning-soft); color: var(--ui-warning); }

.dm-search { margin: 0 var(--ui-space-3) var(--ui-space-3); min-height: 2.75rem; display: flex; align-items: center; gap: var(--ui-space-2); padding: 0 var(--ui-space-3); border: 1px solid var(--ui-border); border-radius: var(--ui-radius-pill); background: var(--ui-surface-soft); color: var(--ui-text-subtle); }
.dm-search input { min-width: 0; width: 100%; border: 0; outline: 0; background: transparent; color: var(--ui-text); font: inherit; }

.dm-inline-notice { display: flex; gap: var(--ui-space-2); margin: 0 var(--ui-space-3) var(--ui-space-3); padding: var(--ui-space-2) var(--ui-space-3); border-radius: var(--ui-radius-md); background: var(--ui-info-soft); color: var(--ui-info); font-size: var(--ui-text-xs); }
.dm-inline-notice--privacy, .dm-inline-notice--warning { background: var(--ui-warning-soft); color: var(--ui-warning); }
.dm-inline-notice--error { background: var(--ui-danger-soft); color: var(--ui-danger); }

.conversation-list { min-height: 0; flex: 1; overflow-y: auto; padding: 0 var(--ui-space-2) var(--ui-space-3); }
.conversation-list__content { min-height: 100%; }
.conversation-skeleton { display: grid; gap: .35rem; padding-top: .15rem; }
.conversation-skeleton__label { padding: .35rem .65rem .55rem; color: var(--ui-text-subtle); font-size: var(--ui-text-xs); }
.conversation-skeleton__row { min-height: 3.8rem; display: grid; grid-template-columns: 2.35rem minmax(0, 1fr); align-items: center; gap: .625rem; padding: .4rem .6rem; }
.conversation-skeleton__avatar { width: 2.35rem; height: 2.35rem; border-radius: 50%; }
.conversation-skeleton__copy { min-width: 0; display: grid; gap: .42rem; }
.conversation-skeleton__line { width: min(78%, 11rem); height: .7rem; border-radius: var(--ui-radius-pill); }
.conversation-skeleton__line--name { width: min(58%, 8rem); height: .78rem; }
.conversation-card { width: 100%; min-height: 4.4rem; display: grid; grid-template-columns: 2.75rem minmax(0, 1fr) auto; align-items: center; gap: var(--ui-space-3); padding: var(--ui-space-2) var(--ui-space-3); border: 0; border-radius: var(--ui-radius-lg); background: transparent; color: var(--ui-text); text-align: left; cursor: pointer; }
.conversation-card:hover { background: var(--ui-surface-muted); }
.conversation-card--active { background: var(--ui-primary-soft); }
.conversation-avatar { position: relative; width: 2.75rem; height: 2.75rem; display: grid; place-items: center; overflow: visible; border-radius: 50%; background: var(--ui-primary-soft); color: var(--ui-primary); font-weight: 800; }
.conversation-avatar img { width: 100%; height: 100%; border-radius: 50%; object-fit: cover; }
.presence-dot { position: absolute; right: -0.05rem; bottom: 0.05rem; width: 0.7rem; height: 0.7rem; border: 2px solid var(--ui-surface); border-radius: 50%; background: var(--ui-border-strong); }
.presence-dot--online { background: var(--ui-success); }
.conversation-copy { min-width: 0; display: grid; gap: 0.2rem; }
.conversation-copy strong, .conversation-copy small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.conversation-copy small { color: var(--ui-text-subtle); font-size: var(--ui-text-xs); }
.unread-badge { min-width: 1.45rem; height: 1.45rem; display: grid; place-items: center; padding: 0 0.35rem; border-radius: var(--ui-radius-pill); background: var(--ui-primary); color: var(--ui-primary-contrast); font-size: 0.7rem; font-weight: 800; }

.conversation-empty { min-height: 14rem; display: grid; place-items: center; align-content: center; gap: var(--ui-space-2); padding: var(--ui-space-5); text-align: center; color: var(--ui-text-muted); }
.conversation-empty__icon { width: 3rem; height: 3rem; display: grid; place-items: center; border-radius: 50%; background: var(--ui-surface-muted); color: var(--ui-text-subtle); }
.conversation-empty strong { color: var(--ui-text); }
.conversation-empty span { max-width: 17rem; font-size: var(--ui-text-xs); }
.conversation-empty--error .conversation-empty__icon { background: var(--ui-danger-soft); color: var(--ui-danger); }
.conversation-empty .ui-button { margin-top: var(--ui-space-2); }

.dm-conversation { min-width: 0; min-height: 0; display: flex; flex-direction: column; background: var(--ui-bg); }
.dm-conversation__header { min-height: 4.25rem; display: flex; align-items: center; gap: var(--ui-space-3); padding: var(--ui-space-2) var(--ui-space-4); border-bottom: 1px solid var(--ui-border); background: var(--ui-surface); }
.back-button { display: none; width: 2.5rem; height: 2.5rem; place-items: center; border: 1px solid var(--ui-border); border-radius: var(--ui-radius-md); background: var(--ui-surface); color: var(--ui-text-muted); }
.active-persona { min-width: 0; display: flex; align-items: center; gap: var(--ui-space-3); color: var(--ui-text); text-decoration: none; }
.active-persona__avatar { width: 2.55rem; height: 2.55rem; display: grid; place-items: center; overflow: hidden; border-radius: 50%; background: var(--ui-primary-soft); color: var(--ui-primary); font-weight: 800; }
.active-persona__avatar img { width: 100%; height: 100%; object-fit: cover; }
.active-persona__copy { min-width: 0; display: grid; }
.active-persona__copy strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.active-persona__copy small { color: var(--ui-text-subtle); font-size: var(--ui-text-xs); }

.dm-stream { min-height: 0; flex: 1; overflow-y: auto; padding: var(--ui-space-4) clamp(var(--ui-space-3), 4vw, var(--ui-space-8)); }
.dm-stream__loading { min-height: 100%; display: flex; flex-direction: column; justify-content: center; gap: var(--ui-space-3); padding: var(--ui-space-5) 0; color: var(--ui-text-subtle); font-size: var(--ui-text-xs); }
.message-skeleton { width: min(62%, 28rem); height: 3.2rem; border-radius: 1rem; }
.message-skeleton--right { align-self: flex-end; width: min(54%, 24rem); }
.message-skeleton--short { width: min(38%, 17rem); height: 2.65rem; }
.dm-stream__empty { min-height: 100%; display: grid; place-items: center; align-content: center; gap: var(--ui-space-2); text-align: center; color: var(--ui-text-muted); }
.dm-stream__empty--error i { background: var(--ui-danger-soft) !important; color: var(--ui-danger) !important; }
.dm-stream__empty .ui-button { margin-top: var(--ui-space-2); }
.dm-stream__empty i { width: 3.5rem; height: 3.5rem; display: grid; place-items: center; border-radius: 50%; background: var(--ui-primary-soft); color: var(--ui-primary); font-size: var(--ui-text-xl); }
.dm-stream__empty strong { color: var(--ui-text); }
.dm-stream__empty span { max-width: 28rem; font-size: var(--ui-text-sm); }

.composer-state { padding: var(--ui-space-2) var(--ui-space-4); border-top: 1px solid var(--ui-border); background: var(--ui-surface-soft); color: var(--ui-text-muted); font-size: var(--ui-text-xs); text-align: center; }
.dm-placeholder { flex: 1; display: grid; place-items: center; align-content: center; gap: var(--ui-space-3); padding: var(--ui-space-8); text-align: center; }
.dm-placeholder__art { width: 5rem; height: 5rem; display: grid; place-items: center; border-radius: 1.75rem; background: var(--ui-primary-soft); color: var(--ui-primary); font-size: 2rem; transform: rotate(4deg); }
.dm-placeholder h2 { margin: var(--ui-space-2) 0 0; font-size: var(--ui-text-xl); }
.dm-placeholder p { max-width: 32rem; margin: 0; color: var(--ui-text-muted); }

@media (max-width: 760px) {
	.dm-shell { height: calc(100dvh - 8.4rem); grid-template-columns: 1fr; margin-inline: calc(var(--ui-space-3) * -1); border-right: 0; border-left: 0; border-radius: 0; }
	.dm-conversation { display: none; }
	.dm-shell--conversation-open .dm-list { display: none; }
	.dm-shell--conversation-open .dm-conversation { display: flex; }
	.back-button { display: grid; }
	.dm-list { border-right: 0; }
}
</style>
