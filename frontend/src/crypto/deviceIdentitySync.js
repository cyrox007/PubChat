import CryptoService from '@/API/CryptoService';
import {
	clearLocalDeviceIdentity,
	ensureDeviceIdentity,
	generateOneTimePrekeys,
	getDeviceRegistrationPayload,
	markRegistrationUploaded,
	rotateLocalSignedPrekey,
} from '@/crypto/deviceIdentity';

const archiveCurrentSignedPrekey = async () => {
	const db = await new Promise((resolve, reject) => {
		const request = indexedDB.open('pubchat-device-crypto-v1', 1);
		request.onsuccess = () => resolve(request.result);
		request.onerror = () => reject(request.error || new Error('crypto_storage_unavailable'));
	});
	try {
		const readTx = db.transaction('keys', 'readonly');
		const store = readTx.objectStore('keys');
		const get = (key) => new Promise((resolve, reject) => {
			const request = store.get(key);
			request.onsuccess = () => resolve(request.result);
			request.onerror = () => reject(request.error || new Error('crypto_storage_failed'));
		});
		const currentPublic = await get('signed-prekey-public');
		const currentPrivate = await get('signed-prekey-private');
		if (!currentPublic?.id || !currentPrivate) return;
		const writeTx = db.transaction('keys', 'readwrite');
		writeTx.objectStore('keys').put(currentPrivate, `signed-prekey-private:${currentPublic.id}`);
		await new Promise((resolve, reject) => {
			writeTx.oncomplete = () => resolve();
			writeTx.onerror = () => reject(writeTx.error || new Error('crypto_storage_failed'));
			writeTx.onabort = () => reject(writeTx.error || new Error('crypto_storage_aborted'));
		});
	} finally {
		db.close();
	}
};

export const ensureRegisteredDevice = async ({ deviceLabel = null, oneTimePrekeyCount = 20 } = {}) => {
	const payload = await ensureDeviceIdentity({ deviceLabel, oneTimePrekeyCount });
	const response = await CryptoService.registerDevice(payload);
	await markRegistrationUploaded(payload.one_time_prekeys.map((item) => item.id));
	return response.data?.device || null;
};

export const replenishDeviceOneTimePrekeys = async (count = 20) => {
	const current = await getDeviceRegistrationPayload();
	const generated = await generateOneTimePrekeys(count);
	if (!generated.length) return { device_uid: current.device_uid, available_one_time_prekeys: 0 };
	const response = await CryptoService.addOneTimePrekeys(current.device_uid, generated);
	await markRegistrationUploaded(generated.map((item) => item.id));
	return response.data;
};

export const rotateDeviceSignedPrekey = async () => {
	const current = await getDeviceRegistrationPayload();
	await archiveCurrentSignedPrekey();
	const signedPrekey = await rotateLocalSignedPrekey();
	const response = await CryptoService.rotateSignedPrekey(current.device_uid, signedPrekey);
	return response.data?.device || null;
};

export const revokeCurrentCryptoDevice = async () => {
	const current = await getDeviceRegistrationPayload();
	const response = await CryptoService.revokeDevice(current.device_uid);
	await clearLocalDeviceIdentity();
	return response.data;
};
