import CSRFService from "@/API/CSRFService";
import UsersServices from "@/API/UsersService";
import AuthService from "@/API/AuthService";
import { clearAccessToken, setAccessToken } from "@/API/session";
import {
	detachWebPushDeviceBeforeLogout,
	dropLocalWebPushSubscription,
} from "@/pwa/webPush";

const readJSON = (key) => {
	try {
		const value = localStorage.getItem(key);
		return value ? JSON.parse(value) : null;
	} catch {
		return null;
	}
};

const cachedUser = readJSON('user');
const cachedIdentity = readJSON('identity');
const hasSessionHint = localStorage.getItem('auth') === 'true' && Boolean(cachedUser);

export default {
	state: {
		auth: hasSessionHint,
		user: cachedUser,
		identity: cachedIdentity,
        // Cached profile data is only a shell. It is not verified for this tab
        // until login or a fresh /identity/v2/me response succeeds.
        identityValidated: false,
		userStatuses: {},
	},
	getters: {
		isAuth: (state) => state.auth,
		getUser: (state) => state.user,
		getIdentity: (state) => state.identity,
        isIdentityValidated: (state) => state.identityValidated,
		getPersona: (state) => state.identity?.persona || null,
		getAccount: (state) => state.identity?.account || null,
		getAccessRestriction: (state) => state.identity?.access_restriction || null,
		getUserStatus: (state) => (userId) => state.userStatuses[userId],
	},
	mutations: {
		setAuth(state, status) {
			state.auth = status;
			if (status) {
				localStorage.setItem('auth', 'true');
			} else {
				localStorage.removeItem('auth');
			}
		},
		setUser(state, userData) {
			state.user = userData ? { ...userData } : null;
			if (userData) {
				localStorage.setItem('user', JSON.stringify(userData));
			} else {
				localStorage.removeItem('user');
			}
		},
        setIdentityValidated(state, valid) {
            state.identityValidated = Boolean(valid);
        },
		setIdentity(state, identity) {
			state.identity = identity ? { ...identity } : null;
			if (identity) {
				localStorage.setItem('identity', JSON.stringify(identity));
			} else {
				localStorage.removeItem('identity');
			}
		},
		setAccessRestriction(state, restriction) {
			if (!state.identity) state.identity = {};
			state.identity = { ...state.identity, access_restriction: restriction || null };
			localStorage.setItem('identity', JSON.stringify(state.identity));
		},
		setMultipleUserStatuses(state, statuses) {
			state.userStatuses = { ...state.userStatuses, ...statuses };
		},
		clearUserStatus(state, userId) {
			delete state.userStatuses[userId];
		},
	},
	actions: {
		async clearUser({ commit }) {
			// If auth expires, invalidate the local PushSubscription as a privacy
			// boundary. The stale server endpoint will receive 404/410 and be removed.
			clearAccessToken();
			localStorage.removeItem('access_token');
			commit('setUser', null);
			commit('setIdentity', null);
			commit('setAuth', false);
            commit('setIdentityValidated', false);
			// Clear visible identity before waiting for browser push cleanup.
			await dropLocalWebPushSubscription().catch(() => null);
		},
		async applyIdentitySession({ commit, state }, responseData) {
			const previousAccountUid = state.identity?.account?.uid || null;
			const nextAccountUid = responseData.account?.uid || null;
			if (previousAccountUid && nextAccountUid && previousAccountUid !== nextAccountUid) {
				await dropLocalWebPushSubscription().catch(() => null);
			}
			setAccessToken(responseData.access_token);
			localStorage.removeItem('access_token');
			commit('setUser', responseData.user);
			commit('setIdentity', {
				account: responseData.account,
				persona: responseData.persona,
				privacy: responseData.privacy,
				role: responseData.role,
				access_restriction: responseData.access_restriction || null,
			});
			commit('setAuth', true);
            commit('setIdentityValidated', true);
		},
		async logout({ dispatch }) {
			try {
				await detachWebPushDeviceBeforeLogout().catch(() => null);
				await AuthService.logout();
			} finally {
				await dispatch('messenger/disconnectMessenger', null, { root: true });
				await dispatch('chat/disconnectSocket', null, { root: true });
				await dispatch('clearUser');
			}
			return true;
		},
		initializeUser({ commit }) {
            commit('setIdentityValidated', false);
			const user = readJSON('user');
			const identity = readJSON('identity');
			const sessionHint = localStorage.getItem('auth') === 'true';
			localStorage.removeItem('access_token');

			if (sessionHint && user) {
				commit('setAuth', true);
				commit('setUser', user);
				if (identity) commit('setIdentity', identity);
				return;
			}

			commit('setAuth', false);
			commit('setUser', null);
			commit('setIdentity', null);
		},
		async restoreSessionAccess({ commit, dispatch, state }) {
			// Access tokens deliberately live only in memory. After a full page load
			// localStorage can tell us that a session probably exists, but it must not
			// authorize protected views by itself. Rotate the HttpOnly refresh cookie
			// before Vue Router mounts any authenticated route/component.
			if (!state.auth) return false;
			try {
				const response = await AuthService.refresh();
				const accessToken = response.data?.access_token;
				if (!accessToken) throw new Error('refresh_response_missing_access_token');
				setAccessToken(accessToken);
				localStorage.removeItem('access_token');
				if (response.data?.access_restriction !== undefined) {
					commit('setAccessRestriction', response.data.access_restriction || null);
				}
				return true;
			} catch (error) {
				if (error.response?.status === 401) {
					await dispatch('clearUser');
					return false;
				}
				throw error;
			}
		},
		async syncIdentity({ commit, dispatch }) {
			try {
				const response = await AuthService.me();
				commit('setUser', response.data.user);
				commit('setIdentity', {
					account: response.data.account,
					persona: response.data.persona,
					privacy: response.data.privacy,
					role: response.data.role,
					access_restriction: response.data.access_restriction || null,
				});
				commit('setAuth', true);
                commit('setIdentityValidated', true);
				return response.data;
			} catch (error) {
				if (error.response?.status === 401) await dispatch('clearUser');
				throw error;
			}
		},
		async fetchUserStatuses({ commit }, userIds) {
			try {
				await CSRFService.getCSRF();
				const response = await UsersServices.getUserStatuses(userIds);
				if (response.data.status === 'ok') {
					commit('setMultipleUserStatuses', response.data.statuses);
				}
			} catch (error) {
				console.error('Ошибка при получении статусов пользователей:', error);
			}
		},
	},
};
