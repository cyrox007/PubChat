import NotificationService from '@/API/NotificationService';

// Keep the badge current if the realtime connection is unavailable.
const POLL_INTERVAL_MS = 30000;
let pollingTimer = null;
let refreshOnFocus = null;

const normalizeUnread = (value) => Math.max(0, Number(value) || 0);

export default {
	namespaced: true,
	state: {
		unread: 0,
		syncing: false,
		initialized: false,
	},
	getters: {
		unread: (state) => state.unread,
		syncing: (state) => state.syncing,
		initialized: (state) => state.initialized,
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
	},
	actions: {
		async refreshUnread({ commit }) {
			const response = await NotificationService.unreadCount();
			commit('setUnread', response.data.unread);
			commit('setInitialized', true);
			return response.data.unread;
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
			commit('setUnread', 0);
			commit('setInitialized', false);
			commit('setSyncing', false);
		},
        startPolling({ dispatch }) {
            if (pollingTimer) return;
            // Polling is read-only. Reminder sync must not run every 30 sec.
            refreshOnFocus = () => {
                if (document.visibilityState === 'visible') {
                    dispatch('refreshUnread').catch(() => {});
                }
            };
            pollingTimer = window.setInterval(refreshOnFocus, POLL_INTERVAL_MS);
            window.addEventListener('focus', refreshOnFocus);
            document.addEventListener('visibilitychange', refreshOnFocus);
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
