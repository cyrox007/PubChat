import $api from ".";

export default class AuthService {
	static async registration(data) {
		return $api.post('/identity/v2/register', data);
	}

	static async login(data) {
		return $api.post('/identity/v2/login', data);
	}

	static async refresh() {
		return $api.post('/identity/v2/refresh');
	}

	static async logout() {
		return $api.post('/identity/v2/logout');
	}

	static async me() {
		return $api.get('/identity/v2/me');
	}

	static async sessions() {
		return $api.get('/identity/v2/sessions');
	}

	static async revokeSession(sessionUid) {
		return $api.delete(`/identity/v2/sessions/${sessionUid}`);
	}

	static async revokeDevice(deviceUid) {
		return $api.delete(`/identity/v2/devices/${deviceUid}`);
	}

	static async revokeOtherSessions() {
		return $api.post('/identity/v2/sessions/revoke-others');
	}

	static async getProfile(accountUid) {
		return $api.get(`/identity/v2/profiles/${accountUid}`);
	}

	static async updatePersona(data) {
		return $api.patch('/identity/v2/persona', data);
	}

	static async updatePrivacy(data) {
		return $api.patch('/identity/v2/privacy', data);
	}

	// Legacy availability checks remain temporarily while old users/profile APIs
	// are migrated. New registration handles conflicts atomically server-side.
	static async checkUsername(username) {
		return $api.post('/users/check-username', { username });
	}

	static async checkEmail(email) {
		return $api.post('/users/check-email', { email });
	}

	static async getValidAccessToken() {
		return $api.get('/service/check-token');
	}
}
