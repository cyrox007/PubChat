import NotificationService from '@/API/NotificationService';

// Keep the badge current if the realtime connection is unavailable.
const POLL_INTERVAL_MS = 30000;
let pollingTimer = null;
let refreshOnFocus = null;
let observedReplyIds = null;
let inboxRequest = null;
let inboxGeneration = 0;

const normalizeUnread = (value) => Math.max(0, Number(value) || 0);

export default {
	namespaced: true,
	state: {
		unread: 0,
		syncing: false,
		initialized: false,
        spaceSound: true,
	},
	getters: {
		unread: (state) => state.unread,
		syncing: (state) => state.syncing,
		initialized: (state) => state.initialized,
        spaceSound: (state) => state.spaceSound,
	},
	mutations: {
		setUnread(state, value) {
			state.unread = normalizeUnread(value);
		},
		setSyncing(state, value) {
			state.syncing = Boolean(value);
		},
		setInitialized(state, value) {
			state.initialized = Boolean(value);
		},
        setSpaceSound(state, value) {
            state.spaceSound = Boolean(value);
        },
	},
	actions: {
		async refreshUnread({ commit }) {
			const response = await NotificationService.unreadCount();
			commit('setUnread', response.data.unread);
			commit('setInitialized', true);
			return response.data.unread;
		},
        async pollInbox({ commit, rootGetters }) {
            if (!rootGetters.isAuth) return;
            if (inboxRequest) return inboxRequest;
            const generation = inboxGeneration;
            inboxRequest = (async () => {
                const response = await NotificationService.list({ limit: 50 });
                if (generation !== inboxGeneration) return;
                const inbox = response.data?.notifications || [];
                const replies = inbox.filter((item) => item.kind === 'space_reply' && item.uid);
                if (observedReplyIds !== null && document.visibilityState === 'visible') {
                    // The original inbox snapshot must not create a storm of
                    // banners for replies received before the tab was opened.
                    const fresh = replies.filter((item) => (
                        !item.is_read && !observedReplyIds.has(item.uid) && item.context_space_uid
                    ));
                    for (const item of fresh.slice(0, 5).reverse()) {
                        commit('messenger/ADD_SPACE_NOTIFICATION', {
                            uid: `space-reply:${item.uid}`,
                            serverNotificationUid: item.uid,
                            surface: 'space',
                            roomUid: item.context_space_uid,
                            timestamp: new Date(item.created_at || Date.now()),
                        }, { root: true });
                    }
                }
                if (observedReplyIds === null) observedReplyIds = new Set();
                for (const item of replies) observedReplyIds.add(item.uid);
                if (observedReplyIds.size > 500) {
                    observedReplyIds = new Set([...observedReplyIds].slice(-300));
                }
                commit('setUnread', response.data?.unread || 0);
                commit('setInitialized', true);
                window.dispatchEvent(new CustomEvent('pubchat:notifications-changed'));
            })().finally(() => { inboxRequest = null; });
            return inboxRequest;
        },
        recordReplyNotice(_, uid) {
            // The first inbox snapshot is always a silent baseline even if a
            // realtime frame was delivered before it finished loading.
            if (uid && observedReplyIds !== null) observedReplyIds.add(uid);
        },
        async refreshSoundPreference({ commit }) {
            const response = await NotificationService.messagePreferences();
            commit('setSpaceSound', response.data?.preferences?.space_sound !== false);
        },
        setSpaceSound({ commit }, value) {
            commit('setSpaceSound', value);
        },
		async sync({ commit, state }) {
			if (state.syncing) return state.unread;
			commit('setSyncing', true);
			try {
				const response = await NotificationService.sync();
				commit('setUnread', response.data.unread);
				commit('setInitialized', true);
				return response.data.unread;
			} finally {
				commit('setSyncing', false);
			}
		},
		setUnread({ commit }, value) {
			commit('setUnread', value);
		},
		decrementUnread({ commit, state }, amount = 1) {
			commit('setUnread', Math.max(0, state.unread - Math.max(0, Number(amount) || 0)));
		},
		clear({ commit }) {
            inboxGeneration += 1;
            observedReplyIds = null;
            inboxRequest = null;
			commit('setUnread', 0);
			commit('setInitialized', false);
			commit('setSyncing', false);
            commit('setSpaceSound', true);
		},
        startPolling({ dispatch }) {
            if (pollingTimer) return;
            // Polling is read-only. Reminder sync must not run every 30 sec.
            refreshOnFocus = () => {
                if (document.visibilityState === 'visible') {
                    dispatch('pollInbox').catch(() => {});
                }
            };
            pollingTimer = window.setInterval(refreshOnFocus, POLL_INTERVAL_MS);
            window.addEventListener('focus', refreshOnFocus);
            document.addEventListener('visibilitychange', refreshOnFocus);
            refreshOnFocus();
        },
        stopPolling() {
            if (pollingTimer) window.clearInterval(pollingTimer);
            pollingTimer = null;
            if (refreshOnFocus) {
                window.removeEventListener('focus', refreshOnFocus);
                document.removeEventListener('visibilitychange', refreshOnFocus);
            }
            refreshOnFocus = null;
        },
	},
};

export { POLL_INTERVAL_MS };
