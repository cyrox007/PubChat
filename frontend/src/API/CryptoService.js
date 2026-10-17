import $api from '.';

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

	static accountDevices(accountUid) {
		return $api.get(`/crypto/v1/accounts/${accountUid}/devices`);
	}

	static prekeyBundle(accountUid) {
		return $api.get(`/crypto/v1/accounts/${accountUid}/prekey-bundle`);
	}

	static sendEncryptedMessage(payload) {
		return $api.post('/crypto/v1/messages', payload);
	}

	static messageEnvelopes(messageUids) {
		return $api.post('/crypto/v1/messages/envelopes', { message_uids: messageUids });
	}
}
