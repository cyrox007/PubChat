import $api from '.';

export default class SocialService {
	static discover(params = {}) {
		return $api.get('/social/v1/discover', { params });
	}

	static availability() {
		return $api.get('/social/v1/availability/me');
	}

	static setAvailability(payload) {
		return $api.put('/social/v1/availability/me', payload);
	}

	static clearAvailability() {
		return $api.delete('/social/v1/availability/me');
	}

	static relationship(accountUid) {
		return $api.get(`/social/v1/relationships/${accountUid}`);
	}

	static follow(accountUid) {
		return $api.post(`/social/v1/follows/${accountUid}`);
	}

	static unfollow(accountUid) {
		return $api.delete(`/social/v1/follows/${accountUid}`);
	}

	static friendAction(accountUid, action) {
		return $api.patch(`/social/v1/friends/${accountUid}`, { action });
	}

	static friends(params = {}) {
		return $api.get('/social/v1/friends', { params });
	}

	static friendRequests(params = {}) {
		return $api.get('/social/v1/friend-requests', { params });
	}

	static block(accountUid) {
		return $api.post(`/social/v1/blocks/${accountUid}`);
	}

	static unblock(accountUid) {
		return $api.delete(`/social/v1/blocks/${accountUid}`);
	}
}
