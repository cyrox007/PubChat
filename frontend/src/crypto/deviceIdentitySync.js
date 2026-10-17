import CryptoService from '@/API/CryptoService';
import {
	clearLocalDeviceIdentity,
	ensureDeviceIdentity,
	generateOneTimePrekeys,
	getDeviceRegistrationPayload,
	markRegistrationUploaded,
	rotateLocalSignedPrekey,
} from '@/crypto/deviceIdentity';

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
