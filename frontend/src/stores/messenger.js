import RealtimeService from '@/API/RealtimeService';
import {
	decryptMessageForCurrentDevice,
	hydrateConversationEnvelopes,
	sendEncryptedText,
} from '@/crypto/messengerE2EE';

let messengerReconnectTimer = null;
let messengerHeartbeatTimer = null;
let messengerConnectionGeneration = 0;

const clearReconnectTimer = () => {
	if (messengerReconnectTimer) clearTimeout(messengerReconnectTimer);
	messengerReconnectTimer = null;
};

const clearHeartbeatTimer = () => {
	if (messengerHeartbeatTimer) clearInterval(messengerHeartbeatTimer);
	messengerHeartbeatTimer = null;
};

const messageKey = (message) => message?.uid || message?.frontId || null;

export default {
	namespaced: true,
	state: {
		socket: null,
		isConnected: false,
		connectionState: 'idle',
		reconnectAttempt: 0,
		realtimeNotice: null,
		activeDialog: null,
		conversations: {},
		unreadCounts: {},
		notifications: [],
		onlineStatuses: {},
		statusSubscriptions: new Set(),
		pendingReadReceipts: new Set(),
	},
	getters: {
		getConversation: (state) => (userId) => state.conversations[userId] || [],
		getUnreadCount: (state) => (userId) => state.unreadCounts[userId] || 0,
		getActiveDialog: (state) => state.activeDialog,
		isConnected: (state) => state.isConnected,
		getConnectionState: (state) => state.connectionState,
		getRealtimeNotice: (state) => state.realtimeNotice,
		getNotifications: (state) => state.notifications,
		hasUnreadNotifications: (state) => state.notifications.length > 0,
		isUserOnline: (state) => (userId) => Boolean(state.onlineStatuses[userId]),
		getOnlineStatuses: (state) => state.onlineStatuses,
	},
	mutations: {
		SET_SOCKET(state, socket) {
			state.socket = socket;
		},
		SET_CONNECTION_STATUS(state, status) {
			state.isConnected = status;
		},
		SET_CONNECTION_STATE(state, status) {
			state.connectionState = status;
		},
		SET_RECONNECT_ATTEMPT(state, attempt) {
			state.reconnectAttempt = attempt;
		},
		SET_REALTIME_NOTICE(state, notice) {
			state.realtimeNotice = notice;
		},
		SET_ACTIVE_DIALOG(state, userId) {
			state.activeDialog = userId;
			if (userId && state.unreadCounts[userId]) state.unreadCounts[userId] = 0;
		},
		ADD_MESSAGE(state, { userId, message }) {
			if (!state.conversations[userId]) state.conversations[userId] = [];
			const key = messageKey(message);
			const existingIndex = key
				? state.conversations[userId].findIndex((item) => messageKey(item) === key)
				: -1;
			if (existingIndex >= 0) {
				state.conversations[userId][existingIndex] = {
					...state.conversations[userId][existingIndex],
					...message,
				};
				return;
			}
			state.conversations[userId].push(message);
			if (state.activeDialog !== userId && !message.isCurrentUser) {
				state.unreadCounts[userId] = (state.unreadCounts[userId] || 0) + 1;
				const shouldNotify = message.notification?.notify_in_app ?? true;
				if (shouldNotify) {
					state.notifications.push({
						uid: message.uid,
						surface: 'messenger',
						sender: message.sender,
						content: message.content,
						timestamp: message.timestamp,
						userId,
					});
				}
			}
		},
		ADD_SPACE_NOTIFICATION(state, notification) {
			const key = notification.uid;
			if (key && state.notifications.some((item) => item.uid === key)) return;
			state.notifications.push(notification);
		},
		MERGE_CONVERSATION(state, { userId, messages }) {
			if (!state.conversations[userId]) state.conversations[userId] = [];
			messages.forEach((message) => {
				const key = messageKey(message);
				const index = key
					? state.conversations[userId].findIndex((item) => messageKey(item) === key)
					: -1;
				if (index >= 0) state.conversations[userId][index] = { ...state.conversations[userId][index], ...message };
				else state.conversations[userId].push(message);
			});
			state.conversations[userId].sort((a, b) => {
				const left = new Date(a.created_at || a.timestamp || 0).getTime();
				const right = new Date(b.created_at || b.timestamp || 0).getTime();
				return left - right;
			});
		},
		CLEAR_NOTIFICATIONS(state) {
			state.notifications = [];
		},
		CLEAR_CONVERSATION(state, userId) {
			delete state.conversations[userId];
		},
		MARK_MESSAGE_AS_READ(state, messageId) {
			Object.values(state.conversations).forEach((messages) => {
				const message = messages.find((item) => item.uid === messageId);
				if (message) message.is_read = true;
			});
		},
		UPDATE_ONLINE_STATUS(state, { userId, isOnline }) {
			state.onlineStatuses[userId] = isOnline;
		},
		UPDATE_STATUS_SUBSCRIPTIONS(state, { userIds, subscribe }) {
			userIds.forEach((userId) => {
				if (subscribe) state.statusSubscriptions.add(userId);
				else state.statusSubscriptions.delete(userId);
			});
		},
		CLEAR_STATUS_SUBSCRIPTIONS(state) {
			state.statusSubscriptions.clear();
		},
		ADD_PENDING_READ(state, messageId) {
			state.pendingReadReceipts.add(messageId);
		},
		REMOVE_PENDING_READ(state, messageId) {
			state.pendingReadReceipts.delete(messageId);
		},
	},
	actions: {
		async connectMessenger({ commit, state, dispatch }) {
			clearReconnectTimer();
			clearHeartbeatTimer();
			messengerConnectionGeneration += 1;
			const generation = messengerConnectionGeneration;

			if (state.socket) {
				try { state.socket.close(1000, 'Replacing connection'); } catch { /* noop */ }
				commit('SET_SOCKET', null);
			}

			commit('SET_CONNECTION_STATUS', false);
			commit('SET_CONNECTION_STATE', state.reconnectAttempt ? 'reconnecting' : 'connecting');

			try {
				const prepared = await RealtimeService.prepareSocket('messenger');
				if (generation !== messengerConnectionGeneration) {
					prepared.socket.close(1000, 'Stale connection');
					return;
				}

				const socket = prepared.socket;
				commit('SET_SOCKET', socket);

				socket.onopen = () => {
					if (generation !== messengerConnectionGeneration) return;
					commit('SET_CONNECTION_STATE', 'authenticating');
					socket.send(JSON.stringify({
						type: 'auth',
						ticket: prepared.ticket,
						resume_token: state.activeDialog || null,
					}));
				};

				socket.onmessage = (event) => {
					if (generation !== messengerConnectionGeneration) return;
					try {
						const data = JSON.parse(event.data);
						if (data.type === 'realtime_ready') {
							commit('SET_CONNECTION_STATUS', true);
							commit('SET_CONNECTION_STATE', 'connected');
							commit('SET_RECONNECT_ATTEMPT', 0);
							commit('SET_REALTIME_NOTICE', null);
							clearHeartbeatTimer();
							const heartbeatMs = Math.max(10, data.heartbeat_seconds || 25) * 1000;
							messengerHeartbeatTimer = setInterval(() => {
								if (socket.readyState === WebSocket.OPEN) {
									socket.send(JSON.stringify({ type: 'heartbeat', action: 'heartbeat' }));
								}
							}, heartbeatMs);
							dispatch('restoreStatusSubscriptions');
							dispatch('flushPendingReadReceipts');
							if (state.activeDialog) {
								dispatch('requestConversation', {
									otherUserId: state.activeDialog,
									requestId: `resume-${Date.now()}`,
								});
							}
							return;
						}
						dispatch('handleMessengerMessage', data);
					} catch (error) {
						console.error('Ошибка messenger realtime frame:', error);
					}
				};

				socket.onclose = (event) => {
					if (generation !== messengerConnectionGeneration) return;
					clearHeartbeatTimer();
					commit('SET_SOCKET', null);
					commit('SET_CONNECTION_STATUS', false);
					if (event.code === 1000) {
						commit('SET_CONNECTION_STATE', 'idle');
						return;
					}
					dispatch('scheduleReconnect');
				};

				socket.onerror = () => {
					if (generation === messengerConnectionGeneration) commit('SET_CONNECTION_STATUS', false);
				};
			} catch (error) {
				console.error('Не удалось подготовить messenger realtime:', error);
				if (generation === messengerConnectionGeneration) dispatch('scheduleReconnect');
			}
		},

		scheduleReconnect({ commit, state, dispatch }) {
			clearReconnectTimer();
			const attempt = state.reconnectAttempt + 1;
			commit('SET_RECONNECT_ATTEMPT', attempt);
			commit('SET_CONNECTION_STATE', navigator.onLine ? 'reconnecting' : 'offline');
			const baseDelay = Math.min(1000 * (2 ** Math.min(attempt - 1, 5)), 30000);
			messengerReconnectTimer = setTimeout(
				() => dispatch('connectMessenger'),
				baseDelay + Math.floor(Math.random() * 400),
			);
		},

		reconnectIfNeeded({ state, dispatch }) {
			if (!state.isConnected) dispatch('connectMessenger');
		},

		disconnectMessenger({ commit, state }) {
			messengerConnectionGeneration += 1;
			clearReconnectTimer();
			clearHeartbeatTimer();
			if (state.socket) {
				try { state.socket.close(1000, 'Client disconnect'); } catch { /* noop */ }
			}
			commit('SET_SOCKET', null);
			commit('SET_CONNECTION_STATUS', false);
			commit('SET_CONNECTION_STATE', 'idle');
			commit('SET_RECONNECT_ATTEMPT', 0);
		},

		async handleMessengerMessage({ commit, rootGetters, state, dispatch }, data) {
			const currentUser = rootGetters.getUser;
			switch (data.type) {
				case 'private_message': {
					const decoded = data.content_type === 'e2ee'
						? await decryptMessageForCurrentDevice(data)
						: data;
					const isFromCurrentUser = decoded.sender_uid === currentUser?.uid;
					const otherUserId = isFromCurrentUser ? decoded.receiver_uid : decoded.sender_uid;
					commit('ADD_MESSAGE', {
						userId: otherUserId,
						message: {
							...decoded,
							isCurrentUser: isFromCurrentUser,
							timestamp: new Date(decoded.created_at || Date.now()),
						},
					});
					const shouldPlaySound = decoded.notification?.play_sound
						?? (!isFromCurrentUser && state.activeDialog !== otherUserId);
					if (!isFromCurrentUser && shouldPlaySound) dispatch('playNotificationSound');
					break;
				}
				case 'space_message_notification': {
					const shouldNotify = data.notification?.notify_in_app ?? true;
					if (shouldNotify) {
						commit('ADD_SPACE_NOTIFICATION', {
							uid: `space:${data.message_uid || `${data.room_uid}:${data.created_at}`}`,
							surface: 'space',
							sender: data.sender,
							content: 'Новое сообщение в чате пространства',
							timestamp: new Date(data.created_at || Date.now()),
							roomUid: data.room_uid,
						});
					}
					if (data.notification?.play_sound ?? true) dispatch('playSpaceNotificationSound');
					break;
				}
				case 'message_read':
					commit('MARK_MESSAGE_AS_READ', data.message_uid);
					break;
				case 'conversation': {
					const hydrated = await hydrateConversationEnvelopes(data.messages || []);
					const messages = [...hydrated].reverse().map((message) => ({
						...message,
						isCurrentUser: message.sender_uid === currentUser?.uid,
						timestamp: new Date(message.created_at || Date.now()),
					}));
					commit('MERGE_CONVERSATION', { userId: data.other_user_uid, messages });
					break;
				}
				case 'status_update':
					Object.entries(data.statuses || {}).forEach(([userId, isOnline]) => {
						commit('UPDATE_ONLINE_STATUS', { userId, isOnline });
					});
					break;
				case 'ping':
					if (state.socket?.readyState === WebSocket.OPEN) {
						state.socket.send(JSON.stringify({ type: 'pong' }));
					}
					break;
				case 'rate_limited':
					commit('SET_REALTIME_NOTICE', {
						type: 'warning',
						message: 'Слишком много сообщений подряд. Попробуйте через несколько секунд.',
					});
					break;
				case 'error':
					commit('SET_REALTIME_NOTICE', {
						type: data.error_type === 'dm_not_allowed' ? 'privacy' : 'error',
						message: data.error_type === 'dm_not_allowed'
							? 'Этот человек принимает личные сообщения только в выбранном им режиме общения.'
							: 'Не удалось выполнить действие.',
					});
					break;
				default:
					break;
			}
		},

		setActiveDialog({ commit }, userId) {
			commit('SET_ACTIVE_DIALOG', userId);
		},

		async sendPrivateMessage({ state, commit }, messageData) {
			const canEncrypt = (messageData.content_type || 'text') === 'text'
				&& typeof messageData.content === 'string'
				&& messageData.content.length > 0;
			if (canEncrypt) {
				try {
					const result = await sendEncryptedText({
						receiverUid: messageData.receiver_uid,
						text: messageData.content,
						frontId: messageData.frontId,
						deviceLabel: navigator.userAgentData?.platform || navigator.platform || 'Browser',
					});
					if (result.encrypted) return result;
					if (result.reason !== 'peer_no_crypto_devices') throw new Error(result.reason || 'e2ee_unavailable');
				} catch (error) {
					if (error?.message !== 'peer_no_crypto_devices') {
						commit('SET_REALTIME_NOTICE', {
							type: 'error',
							message: 'Защищённая отправка не удалась. Сообщение не было отправлено без шифрования.',
						});
						throw error;
					}
				}
			}
			if (state.socket?.readyState !== WebSocket.OPEN || state.connectionState !== 'connected') {
				throw new Error('Личные сообщения сейчас переподключаются');
			}
			state.socket.send(JSON.stringify({ action: 'send_message', ...messageData }));
			return { encrypted: false };
		},

		requestConversation({ state }, { otherUserId, requestId }) {
			if (state.socket?.readyState !== WebSocket.OPEN || state.connectionState !== 'connected') return;
			state.socket.send(JSON.stringify({
				action: 'get_conversation',
				other_user_uid: otherUserId,
				request_id: requestId,
			}));
		},

		markMessageAsRead({ state, commit }, messageId) {
			if (state.socket?.readyState === WebSocket.OPEN && state.connectionState === 'connected') {
				state.socket.send(JSON.stringify({ action: 'mark_message_as_read', message_uid: messageId }));
				return;
			}
			commit('ADD_PENDING_READ', messageId);
		},

		flushPendingReadReceipts({ state, commit }) {
			if (state.socket?.readyState !== WebSocket.OPEN || state.connectionState !== 'connected') return;
			[...state.pendingReadReceipts].forEach((messageId) => {
				state.socket.send(JSON.stringify({ action: 'mark_message_as_read', message_uid: messageId }));
				commit('REMOVE_PENDING_READ', messageId);
			});
		},

		playNotificationSound() {
			const audio = new Audio('/sounds/private_notification.mp3');
			audio.preload = 'auto';
			audio.play().catch(() => {});
		},

		playSpaceNotificationSound() {
			const audio = new Audio('/sounds/chat_notification.mp3');
			audio.preload = 'auto';
			audio.play().catch(() => {});
		},

		clearNotifications({ commit }) {
			commit('CLEAR_NOTIFICATIONS');
		},

		subscribeToStatuses({ commit, state }, userIds) {
			const normalized = [...new Set(userIds || [])];
			commit('UPDATE_STATUS_SUBSCRIPTIONS', { userIds: normalized, subscribe: true });
			if (state.socket?.readyState === WebSocket.OPEN && state.connectionState === 'connected') {
				state.socket.send(JSON.stringify({ action: 'subscribe_status', userIds: normalized }));
			}
		},

		unsubscribeFromStatuses({ commit, state }, userIds) {
			const normalized = [...new Set(userIds || [])];
			commit('UPDATE_STATUS_SUBSCRIPTIONS', { userIds: normalized, subscribe: false });
			if (state.socket?.readyState === WebSocket.OPEN && state.connectionState === 'connected') {
				state.socket.send(JSON.stringify({ action: 'unsubscribe_status', userIds: normalized }));
			}
		},

		restoreStatusSubscriptions({ state }) {
			if (!state.statusSubscriptions.size || state.socket?.readyState !== WebSocket.OPEN) return;
			state.socket.send(JSON.stringify({
				action: 'subscribe_status',
				userIds: [...state.statusSubscriptions],
			}));
		},
	},
};