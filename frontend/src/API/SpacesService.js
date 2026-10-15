import $api from '.';

const hasTimezone = (value) => /(?:Z|[+-]\d{2}:\d{2})$/i.test(value);

const normalizeUtcTimestamps = (value, key = '') => {
	if (Array.isArray(value)) return value.map((item) => normalizeUtcTimestamps(item));
	if (value && typeof value === 'object') {
		return Object.fromEntries(
			Object.entries(value).map(([childKey, childValue]) => [childKey, normalizeUtcTimestamps(childValue, childKey)]),
		);
	}
	if (typeof value === 'string' && key.endsWith('_at') && !hasTimezone(value)) return `${value}Z`;
	return value;
};

const spaceRequest = (promise) => promise.then((response) => {
	response.data = normalizeUtcTimestamps(response.data);
	return response;
});

export default class SpacesService {
	static list(params = {}) {
		return spaceRequest($api.get('/spaces/v1', { params }));
	}

	static get(spaceUid) {
		return spaceRequest($api.get(`/spaces/v1/${spaceUid}`));
	}

	static pulse(spaceUid) {
		return spaceRequest($api.get(`/spaces/v1/${spaceUid}/pulse`));
	}

	static create(payload) {
		return spaceRequest($api.post('/spaces/v1', payload));
	}

	static update(spaceUid, payload) {
		return spaceRequest($api.patch(`/spaces/v1/${spaceUid}`, payload));
	}

	static archive(spaceUid) {
		return $api.delete(`/spaces/v1/${spaceUid}`);
	}

	static join(spaceUid) {
		return spaceRequest($api.post(`/spaces/v1/${spaceUid}/join`));
	}

	static leave(spaceUid) {
		return $api.delete(`/spaces/v1/${spaceUid}/membership`);
	}

	static members(spaceUid, params = {}) {
		return spaceRequest($api.get(`/spaces/v1/${spaceUid}/members`, { params }));
	}

	static updateMemberRole(spaceUid, accountUid, role) {
		return spaceRequest($api.patch(`/spaces/v1/${spaceUid}/members/${accountUid}`, { role }));
	}

	static manageMembership(spaceUid, accountUid, action) {
		return spaceRequest($api.patch(`/spaces/v1/${spaceUid}/members/${accountUid}/membership`, { action }));
	}

	static invite(spaceUid, accountUid) {
		return spaceRequest($api.post(`/spaces/v1/${spaceUid}/invitations/${accountUid}`));
	}

	static revokeInvitation(spaceUid, accountUid) {
		return $api.delete(`/spaces/v1/${spaceUid}/invitations/${accountUid}`);
	}

	static invitations(params = {}) {
		return spaceRequest($api.get('/spaces/v1/invitations', { params }));
	}

	static respondInvitation(invitationUid, action) {
		return spaceRequest($api.patch(`/spaces/v1/invitations/${invitationUid}`, { action }));
	}

	static rules(spaceUid) {
		return spaceRequest($api.get(`/spaces/v1/${spaceUid}/rules`));
	}

	static createRule(spaceUid, payload) {
		return spaceRequest($api.post(`/spaces/v1/${spaceUid}/rules`, payload));
	}

	static updateRule(spaceUid, ruleUid, payload) {
		return spaceRequest($api.patch(`/spaces/v1/${spaceUid}/rules/${ruleUid}`, payload));
	}

	static deleteRule(spaceUid, ruleUid) {
		return $api.delete(`/spaces/v1/${spaceUid}/rules/${ruleUid}`);
	}

	static events(spaceUid, params = {}) {
		return spaceRequest($api.get(`/spaces/v1/${spaceUid}/events`, { params }));
	}

	static createEvent(spaceUid, payload) {
		return spaceRequest($api.post(`/spaces/v1/${spaceUid}/events`, payload));
	}

	static updateEvent(spaceUid, eventUid, payload) {
		return spaceRequest($api.patch(`/spaces/v1/${spaceUid}/events/${eventUid}`, payload));
	}

	static deleteEvent(spaceUid, eventUid) {
		return $api.delete(`/spaces/v1/${spaceUid}/events/${eventUid}`);
	}

	static history(spaceUid, params = {}) {
		return spaceRequest($api.get(`/spaces/v1/${spaceUid}/history`, { params }));
	}
}
