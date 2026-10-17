import $api from '.';
import MessengerService from '@/API/MessengerService';
import { assertDirectoryCheckpoint } from '@/crypto/directoryCheckpoint';

export default class CryptoService {
	static registerDevice(payload) {
		return $api.post('/crypto/v1/devices', payload);
	}

	static devices() {
		return $api.get('/crypto/v1/devices');
	}

	static rotateSignedPrekey(deviceUid, signedPrekey) {
		return $api.put(`/crypto/v1/devices/${deviceUid}/signed-prekey`, { signed_prekey: signedPrekey });
	}

	static addOneTimePrekeys(deviceUid, oneTimePrekeys) {
		return $api.post(`/crypto/v1/devices/${deviceUid}/one-time-prekeys`, {
			one_time_prekeys: oneTimePrekeys,
		});
	}

	static revokeDevice(deviceUid) {
		return $api.delete(`/crypto/v1/devices/${deviceUid}`);
	}

	static async accountDevices(accountUid) {
		const policyResponse = await MessengerService.getConversationEncryption(accountUid);
		const policy = policyResponse.data?.encryption || {};
		if (policy.effective_mode === 'plaintext') {
			return { data: { status: 'ok', account_uid: accountUid, devices: [], encryption: policy, directory_checkpoint: null } };
		}
		if (policy.effective_mode === 'e2ee' && Number(policy.peer_crypto_devices || 0) < 1) {
			const error = new Error('e2ee_devices_not_ready');
			error.code = 'e2ee_devices_not_ready';
			throw error;
		}
		const response = await $api.get(`/crypto/v1/accounts/${accountUid}/devices`);
		const devices = response.data?.devices || [];
		await assertDirectoryCheckpoint({
			accountUid,
			checkpoint: response.data?.directory_checkpoint || null,
			requireCheckpoint: devices.length > 0,
			historyLoader: async (afterSequence, limit) => {
				const historyResponse = await $api.get(`/crypto/v1/accounts/${accountUid}/directory-history`, {
					params: { after_sequence: afterSequence, limit },
				});
				return historyResponse.data?.events || [];
			},
		});
		return response;
	}

	static directoryHistory(accountUid, afterSequence = 0, limit = 200) {
		return $api.get(`/crypto/v1/accounts/${accountUid}/directory-history`, {
			params: { after_sequence: Math.max(0, Number(afterSequence) || 0), limit: Math.max(1, Math.min(200, Number(limit) || 200)) },
		});
	}

	static prekeyBundle(accountUid) {
		return $api.get(`/crypto/v1/accounts/${accountUid}/prekey-bundle`);
	}

	static uploadEncryptedAttachment(attachmentUid, ciphertext) {
		const form = new FormData();
		form.append('file', new Blob([ciphertext], { type: 'application/octet-stream' }), 'ciphertext.bin');
		return $api.post(`/crypto/v1/attachments/${attachmentUid}`, form);
	}

	static encryptedAttachment(attachmentUid) {
		return $api.get(`/crypto/v1/attachments/${attachmentUid}`, { responseType: 'arraybuffer' });
	}

	static deleteEncryptedAttachment(attachmentUid) {
		return $api.delete(`/crypto/v1/attachments/${attachmentUid}`);
	}

	static sendEncryptedMessage(payload) {
		return $api.post('/crypto/v1/messages', payload);
	}

	static messageEnvelopes(messageUids) {
		return $api.post('/crypto/v1/messages/envelopes', { message_uids: messageUids });
	}
}
