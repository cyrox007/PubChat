import $api from ".";

export default class MessengerService {
	static async getDialogs() {
		return await $api.get('/messenger/dialogs');
	}

	static async getConversationEncryption(peerUid) {
		return await $api.get(`/messenger/conversations/${peerUid}/encryption`);
	}

	static async setConversationEncryption(peerUid, mode) {
		return await $api.put(`/messenger/conversations/${peerUid}/encryption`, { mode });
	}
};