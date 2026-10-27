import UsersService from '@/API/UsersService';
import RealtimeService from '@/API/RealtimeService';
import { upsertMessage, sameMessage } from '@/utils/messageIdentity.js';

let roomReconnectTimer = null;
let roomHeartbeatTimer = null;
let roomConnectTimer = null;

const clearConnectTimer = () => {
	if (roomConnectTimer) clearTimeout(roomConnectTimer);
	roomConnectTimer = null;
};
let roomConnectionGeneration = 0;

const clearReconnectTimer = () => {
	if (roomReconnectTimer) clearTimeout(roomReconnectTimer);
	roomReconnectTimer = null;
};

const clearHeartbeatTimer = () => {
	if (roomHeartbeatTimer) clearInterval(roomHeartbeatTimer);
	roomHeartbeatTimer = null;
};

const messageKey = (message) => message?.frontId || message?.uid || message?.tempId || null;

export default {
	namespaced: true,
	state: {
		currentRoom: null,
		connectedUsers: [],
		socket: null,
		isConnected: false,
		connectionState: 'idle',
		reconnectAttempt: 0,
		intendedRoomId: null,
		realtimeNotice: null,
		messages: [],
		notifications: [],
		unreadReplies: [],
		muteStatus: null,
	},
	getters: {
		getCurrentRoom: (state) => state.currentRoom,
		getConnectedUsers: (state) => state.connectedUsers,
		isConnected: (state) => state.isConnected,
		getConnectionState: (state) => state.connectionState,
		getRealtimeNotice: (state) => state.realtimeNotice,
		getMessages: (state) => state.messages,
		unreadReplies: (state) => state.unreadReplies,
		hasUnreadReplies: (state) => state.unreadReplies.length > 0,
		isUserMuted: (state) => Boolean(state.muteStatus && state.muteStatus.status === 'muted'),
		getMuteDetails: (state) => state.muteStatus?.details || null,
		isCurrentUserOwner: (state, getters, rootState, rootGetters) => {
			return state.currentRoom?.owner_uid === rootGetters.getUser?.uid;
		},
		isCurrentUserModerator: (state, getters, rootState, rootGetters) => {
			return state.currentRoom?.moderators?.includes(rootGetters.getUser?.uid) || false;
		},
		canManageUsers: (state, getters) => getters.isCurrentUserOwner || getters.isCurrentUserModerator,
	},
	mutations: {
		setCurrentRoom(state, room) {
			state.currentRoom = room;
		},
		clearCurrentRoom(state) {
			state.currentRoom = null;
		},
		setConnectedUsers(state, users) {
			state.connectedUsers = users;
		},
		setSocket(state, socket) {
			state.socket = socket;
		},
		setConnectionStatus(state, status) {
			state.isConnected = status;
		},
		setConnectionState(state, status) {
			state.connectionState = status;
		},
		setReconnectAttempt(state, attempt) {
			state.reconnectAttempt = attempt;
		},
		setIntendedRoomId(state, roomId) {
			state.intendedRoomId = roomId;
		},
		setRealtimeNotice(state, notice) {
			state.realtimeNotice = notice;
		},
		addMessage(state, message) {
            state.messages = upsertMessage(state.messages, message);
        },
        SET_MESSAGE_STATUS(state, { frontId, status }) {
            state.messages = state.messages.map((m) => m.frontId === frontId && !m.uid
                ? { ...m, status }
                : m);
        },
        MARK_UNCONFIRMED(state) {
            state.messages = state.messages.map((m) => m.status === 'sending' && !m.uid
                ? { ...m, status: 'uncertain' }
                : m);
        },
		mergeMessages(state, messages) {
            for (const message of messages) {
                state.messages = upsertMessage(state.messages, message);
            }
			state.messages.sort((a, b) => {
				const left = new Date(a.created_at || a.timestamp || 0).getTime();
				const right = new Date(b.created_at || b.timestamp || 0).getTime();
				return left - right;
			});
		},
		clearMessages(state) {
			state.messages = [];
		},
		ADD_UNREAD_REPLY(state, reply) {
			if (!state.unreadReplies.some((item) => messageKey(item) === messageKey(reply))) {
				state.unreadReplies.push(reply);
			}
		},
		CLEAR_UNREAD_REPLIES(state) {
			state.unreadReplies = [];
		},
		setMuteStatus(state, status) {
			state.muteStatus = status;
		},
		clearMuteStatus(state) {
			state.muteStatus = null;
		},
		addModerator(state, userUid) {
			if (!state.currentRoom) return;
			if (!Array.isArray(state.currentRoom.moderators)) state.currentRoom.moderators = [];
			if (!state.currentRoom.moderators.includes(userUid)) state.currentRoom.moderators.push(userUid);
		},
		removeModerator(state, userUid) {
			if (state.currentRoom?.moderators) {
				state.currentRoom.moderators = state.currentRoom.moderators.filter((uid) => uid !== userUid);
			}
		},
		removeUser(state, userUid) {
			state.connectedUsers = state.connectedUsers.filter((user) => user.uid !== userUid);
		},
		updateModerators(state, moderators) {
			if (state.currentRoom) state.currentRoom.moderators = moderators;
		},
	},
	actions: {
		async fetchUserData(_, userUids) {
			try {
				const response = await UsersService.get_users_by_uids(userUids);
				return response.data.status === 'ok' ? response.data.users : [];
			} catch (error) {
				console.error('Не удалось загрузить Persona участников:', error);
				return [];
			}
		},

		async connectSocket({ commit, state, dispatch }, payload) {
			const roomId = typeof payload === 'string' ? payload : payload?.roomId;
			const isReconnect = typeof payload === 'object' && payload?.reconnect;
			if (!roomId) return;

            // Room view and authenticated bootstrap may request the same room.
            // Keep the existing ticket/handshake instead of cancelling it.
            if (state.intendedRoomId === roomId && (
                roomConnectTimer || [WebSocket.CONNECTING, WebSocket.OPEN].includes(state.socket?.readyState)
            )) return;

			clearReconnectTimer();
			clearHeartbeatTimer();
			clearConnectTimer();
			roomConnectionGeneration += 1;
			const generation = roomConnectionGeneration;

			if (state.socket) {
				try { state.socket.close(1000, 'Replacing connection'); } catch { /* noop */ }
				commit('setSocket', null);
			}

			commit('setIntendedRoomId', roomId);
			commit('setConnectionStatus', false);
			commit('setConnectionState', isReconnect ? 'reconnecting' : 'connecting');
			commit('setRealtimeNotice', null);

            // Cover ticket retrieval, TCP/TLS establishment and the auth frame.
            // Invalidate this attempt before closing so a late result cannot win.
            roomConnectTimer = setTimeout(() => {
                if (generation !== roomConnectionGeneration) return;
                roomConnectionGeneration += 1;
                roomConnectTimer = null;
                const stalledSocket = state.socket;
                commit('setSocket', null);
                commit('setConnectionStatus', false);
                try { stalledSocket?.close(4000, 'Connection timeout'); } catch { /* noop */ }
                dispatch('scheduleReconnect', roomId);
            }, 15000);

			try {
				const prepared = await RealtimeService.prepareSocket('room', roomId);
				if (generation !== roomConnectionGeneration) {
					prepared.socket.close(1000, 'Stale connection');
					return;
				}

				const socket = prepared.socket;
				commit('setSocket', socket);

				socket.onopen = () => {
					if (generation !== roomConnectionGeneration) return;
					commit('setConnectionState', 'authenticating');
					const lastMessage = state.messages[state.messages.length - 1];
					socket.send(JSON.stringify({
						type: 'auth',
						ticket: prepared.ticket,
						resume_token: lastMessage?.uid || null,
					}));
				};

				socket.onmessage = (event) => {
					if (generation !== roomConnectionGeneration) return;
					try {
						const data = JSON.parse(event.data);
						if (data.type === 'realtime_ready') {
							commit('setConnectionStatus', true);
							commit('setConnectionState', 'connected');
							commit('setReconnectAttempt', 0);
							commit('setRealtimeNotice', null);
							clearHeartbeatTimer();
							clearConnectTimer();
							const heartbeatMs = Math.max(10, data.heartbeat_seconds || 25) * 1000;
							roomHeartbeatTimer = setInterval(() => {
								if (socket.readyState === WebSocket.OPEN) {
									socket.send(JSON.stringify({ type: 'heartbeat' }));
								}
							}, heartbeatMs);
							return;
						}
						dispatch('handleSocketMessage', data);
					} catch (error) {
						console.error('Ошибка realtime frame:', error);
					}
				};

				socket.onclose = (event) => {
					if (generation !== roomConnectionGeneration) return;
					clearHeartbeatTimer();
					clearConnectTimer();
					commit('setSocket', null);
					commit('setConnectionStatus', false);
                    commit('MARK_UNCONFIRMED');

                    // Local disconnect/replacement already invalidated the
                    // connection generation. Remote 1000 still needs reconnect.
                    if (event.code === 4001 || event.code === 4003 || event.code === 1008) {
						commit('setConnectionState', 'restricted');
						commit('setRealtimeNotice', {
							type: 'restricted',
							message: event.reason || 'Доступ к пространству ограничен.',
						});
						return;
					}
					dispatch('scheduleReconnect', roomId);
				};

				socket.onerror = () => {
					if (generation !== roomConnectionGeneration) return;
					commit('setConnectionStatus', false);
				};
			} catch (error) {
				console.error('Не удалось подготовить realtime room socket:', error);
				if (generation !== roomConnectionGeneration) return;
                clearConnectTimer();
				if ([403, 404].includes(error.response?.status)) {
					commit('setConnectionState', 'restricted');
					commit('setRealtimeNotice', {
						type: 'restricted',
						message: 'Доступ к пространству изменился. Вернитесь в discovery и проверьте участие.',
					});
					return;
				}
				dispatch('scheduleReconnect', roomId);
			}
		},

		scheduleReconnect({ commit, state, dispatch }, roomId) {
			clearReconnectTimer();
			const attempt = state.reconnectAttempt + 1;
			commit('setReconnectAttempt', attempt);
			commit('setConnectionState', navigator.onLine ? 'reconnecting' : 'offline');
			const baseDelay = Math.min(1000 * (2 ** Math.min(attempt - 1, 5)), 30000);
			const delay = baseDelay + Math.floor(Math.random() * 400);
			roomReconnectTimer = setTimeout(() => {
				dispatch('connectSocket', { roomId, reconnect: true });
			}, delay);
		},

        reconnectIfNeeded({ state, dispatch }) {
            if (!state.intendedRoomId || state.isConnected || roomConnectTimer
                || [WebSocket.CONNECTING, WebSocket.OPEN].includes(state.socket?.readyState)) return;
            dispatch('connectSocket', { roomId: state.intendedRoomId, reconnect: true });
        },

		async handleSocketMessage({ commit, dispatch, rootGetters, state }, data) {
			const currentUserId = rootGetters.getUser?.uid;
			switch (data.type) {
				case 'message': {
                    commit('addMessage', { ...data, status: 'sent' });
					const isViewingSpace = window.location.pathname.includes('/spaces/');
					if (!isViewingSpace && data.reply_to?.sender?.uid === currentUserId) {
						commit('ADD_UNREAD_REPLY', {
							uid: data.uid,
							sender: data.sender,
							content: data.content,
							room_uid: data.room_uid,
							timestamp: new Date(data.created_at || Date.now()),
						});
						dispatch('playNotificationSound');
					}
					break;
				}
				case 'user_list': {
					const usersData = await dispatch('fetchUserData', data.users || []);
					commit('setConnectedUsers', usersData);
					break;
				}
				case 'initial_data': {
					if (Array.isArray(data.messages)) {
						commit('mergeMessages', [...data.messages].reverse());
					}
					break;
				}
				case 'room_info':
					if (data.room) {
						// Realtime still receives a legacy room projection during the compatibility
						// phase. Keep canonical Space fields from REST authoritative while adding
						// live-only legacy fields such as active restrictions.
						commit('setCurrentRoom', { ...data.room, ...(state.currentRoom || {}) });
					}
					break;
				case 'mute_status':
					commit('setMuteStatus', data);
					break;
				case 'ping':
					if (state.socket?.readyState === WebSocket.OPEN) {
						state.socket.send(JSON.stringify({ type: 'pong' }));
					}
					break;
				case 'duplicate_pending':
                    commit('SET_MESSAGE_STATUS', { frontId: data.frontId, status: 'uncertain' });
                    break;
                case 'rate_limited':
					commit('setRealtimeNotice', {
						type: 'warning',
						message: 'Слишком много сообщений подряд. Небольшая пауза поможет разговору оставаться комфортным.',
					});
					break;
				case 'moderators_updated':
					commit('updateModerators', data.moderators || []);
					break;
				case 'user_banned':
					commit('removeUser', data.target_user_uid);
					if (data.target_user_uid === currentUserId) {
						commit('setRealtimeNotice', {
							type: 'restricted',
							message: data.reason || 'Доступ к пространству ограничен.',
						});
					}
					break;
				case 'moderator_added':
					commit('addModerator', data.target_user_uid);
					break;
				case 'moderator_removed':
					commit('removeModerator', data.target_user_uid);
					break;
				case 'error':
                    if (data.frontId) commit('SET_MESSAGE_STATUS', { frontId: data.frontId, status: 'error' });
					commit('setRealtimeNotice', {
						type: 'error',
						message: 'Действие не выполнено. Попробуйте ещё раз.',
					});
					break;
				default:
					break;
			}
		},

		disconnectSocket({ commit, state }) {
			roomConnectionGeneration += 1;
			clearReconnectTimer();
			clearHeartbeatTimer();
			clearConnectTimer();
			if (state.socket) {
				try { state.socket.close(1000, 'Client disconnect'); } catch { /* noop */ }
			}
			commit('setSocket', null);
			commit('setConnectionStatus', false);
			commit('setConnectionState', 'idle');
			commit('setReconnectAttempt', 0);
			commit('setIntendedRoomId', null);
			commit('setConnectedUsers', []);
		},

		sendMessage({ state, commit }, message) {
            if (state.socket?.readyState !== WebSocket.OPEN || state.connectionState !== 'connected') {
                throw new Error('Пространство сейчас переподключается');
            }
            // Keep the original payload for a user-triggered retry with the SAME frontId.
            const outgoing = { ...message };
            commit('addMessage', {
                ...message, room_uid: state.intendedRoomId, uid: null,
                created_at: new Date().toISOString(), status: 'sending', outgoing,
            });
            try {
                state.socket.send(JSON.stringify(outgoing));
            } catch (error) {
                commit('SET_MESSAGE_STATUS', { frontId: message.frontId, status: 'uncertain' });
                throw error;
            }
        },
        retryMessage({ state, commit }, frontId) {
            const pending = state.messages.find((m) => m.frontId === frontId && !m.uid);
            if (!pending?.outgoing) return;
            if (state.socket?.readyState !== WebSocket.OPEN || state.connectionState !== 'connected') {
                throw new Error('Соединение ещё не восстановлено');
            }
            commit('SET_MESSAGE_STATUS', { frontId, status: 'sending' });
            try {
                state.socket.send(JSON.stringify(pending.outgoing));
            } catch (error) {
                commit('SET_MESSAGE_STATUS', { frontId, status: 'uncertain' });
                throw error;
            }
        },

		clearNotifications({ commit }) {
			commit('CLEAR_UNREAD_REPLIES');
		},

		async switchRoom({ dispatch, commit }, { room, roomId }) {
			await dispatch('disconnectSocket');
			commit('clearMessages');
			commit('CLEAR_UNREAD_REPLIES');
			commit('clearMuteStatus');
			commit('setCurrentRoom', room);
			await dispatch('connectSocket', roomId);
		},

		playNotificationSound() {
			const audio = new Audio('/sounds/chat_notification.mp3');
			audio.preload = 'auto';
			audio.play().catch(() => {});
		},

		sendModeratorAction({ state }, { target_user_uid, action }) {
			if (state.socket?.readyState !== WebSocket.OPEN || state.connectionState !== 'connected') {
				throw new Error('Realtime connection is not ready');
			}
			state.socket.send(JSON.stringify({
				type: 'moderator_action',
				target_user_uid,
				action,
				room_uid: state.currentRoom?.uid,
				timestamp: new Date().toISOString(),
			}));
		},

		sendBanAction({ state }, { target_user_uid, reason, permanent = false }) {
			if (state.socket?.readyState !== WebSocket.OPEN || state.connectionState !== 'connected') {
				throw new Error('Realtime connection is not ready');
			}
			state.socket.send(JSON.stringify({
				type: 'ban_user',
				target_user_uid,
				reason,
				permanent,
			}));
		},
	},
};
