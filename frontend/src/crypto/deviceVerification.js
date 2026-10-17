import CryptoService from '@/API/CryptoService';
import { ensureRegisteredDevice } from '@/crypto/deviceIdentitySync';
import { getDeviceRegistrationPayload } from '@/crypto/deviceIdentity';

const DB_NAME = 'pubchat-e2ee-sessions-v1';
const DB_VERSION = 2;
const encoder = new TextEncoder();

const openDb = () => new Promise((resolve, reject) => {
	const request = indexedDB.open(DB_NAME, DB_VERSION);
	request.onupgradeneeded = () => {
		const db = request.result;
		if (!db.objectStoreNames.contains('sessions')) db.createObjectStore('sessions', { keyPath: 'key' });
		if (!db.objectStoreNames.contains('messageKeys')) db.createObjectStore('messageKeys', { keyPath: 'key' });
		if (!db.objectStoreNames.contains('pins')) db.createObjectStore('pins', { keyPath: 'deviceUid' });
		if (!db.objectStoreNames.contains('verifications')) db.createObjectStore('verifications', { keyPath: 'key' });
		if (!db.objectStoreNames.contains('accountSnapshots')) db.createObjectStore('accountSnapshots', { keyPath: 'accountUid' });
	};
	request.onsuccess = () => resolve(request.result);
	request.onerror = () => reject(request.error || new Error('e2ee_storage_unavailable'));
});

const requestResult = (request) => new Promise((resolve, reject) => {
	request.onsuccess = () => resolve(request.result);
	request.onerror = () => reject(request.error || new Error('e2ee_storage_failed'));
});

const txDone = (tx) => new Promise((resolve, reject) => {
	tx.oncomplete = () => resolve();
	tx.onerror = () => reject(tx.error || new Error('e2ee_storage_failed'));
	tx.onabort = () => reject(tx.error || new Error('e2ee_storage_aborted'));
});

const getRecord = async (storeName, key) => {
	const db = await openDb();
	try {
		return await requestResult(db.transaction(storeName, 'readonly').objectStore(storeName).get(key));
	} finally {
		db.close();
	}
};

const putRecord = async (storeName, value) => {
	const db = await openDb();
	try {
		const tx = db.transaction(storeName, 'readwrite');
		tx.objectStore(storeName).put(value);
		await txDone(tx);
	} finally {
		db.close();
	}
};

const deleteRecord = async (storeName, key) => {
	const db = await openDb();
	try {
		const tx = db.transaction(storeName, 'readwrite');
		tx.objectStore(storeName).delete(key);
		await txDone(tx);
	} finally {
		db.close();
	}
};

const fromBase64Url = (value) => {
	const normalized = String(value || '');
	const padded = normalized.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - normalized.length % 4) % 4);
	const binary = atob(padded);
	return Uint8Array.from(binary, (char) => char.charCodeAt(0));
};

const toBase64Url = (buffer) => {
	const bytes = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer);
	let binary = '';
	for (const byte of bytes) binary += String.fromCharCode(byte);
	return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
};

const concat = (...parts) => {
	const arrays = parts.map((part) => part instanceof Uint8Array ? part : new Uint8Array(part));
	const out = new Uint8Array(arrays.reduce((sum, part) => sum + part.byteLength, 0));
	let offset = 0;
	for (const part of arrays) {
		out.set(part, offset);
		offset += part.byteLength;
	}
	return out;
};

const deviceDescriptor = ({ accountUid, deviceUid, identitySigningKey, identityDhKey }) => ({
	account_uid: String(accountUid),
	device_uid: String(deviceUid),
	identity_signing_key: String(identitySigningKey),
	identity_dh_key: String(identityDhKey),
});

const descriptorBytes = (descriptor) => encoder.encode(JSON.stringify(descriptor));

const computeDeviceFingerprint = async (device) => {
	const digest = await crypto.subtle.digest(
		'SHA-256',
		concat(
			encoder.encode('pubchat-device-identity-v1\0'),
			fromBase64Url(device.identity_signing_key),
			fromBase64Url(device.identity_dh_key),
		),
	);
	return toBase64Url(digest);
};

const safetyDigest = async ({ ownAccountUid, own, peerAccountUid, peer }) => {
	const descriptors = [
		deviceDescriptor({
			accountUid: ownAccountUid,
			deviceUid: own.device_uid,
			identitySigningKey: own.identity_signing_key,
			identityDhKey: own.identity_dh_key,
		}),
		deviceDescriptor({
			accountUid: peerAccountUid,
			deviceUid: peer.device_uid,
			identitySigningKey: peer.identity_signing_key,
			identityDhKey: peer.identity_dh_key,
		}),
	].sort((left, right) => `${left.account_uid}:${left.device_uid}`.localeCompare(`${right.account_uid}:${right.device_uid}`));
	return new Uint8Array(await crypto.subtle.digest(
		'SHA-256',
		concat(
			encoder.encode('pubchat-safety-number-v1\0'),
			descriptorBytes(descriptors[0]),
			encoder.encode('\0'),
			descriptorBytes(descriptors[1]),
		),
	));
};

const formatSafetyNumber = (digest) => {
	const view = new DataView(digest.buffer, digest.byteOffset, digest.byteLength);
	const groups = [];
	for (let offset = 0; offset < digest.byteLength; offset += 4) {
		groups.push(String(view.getUint32(offset, false) % 100000).padStart(5, '0'));
	}
	return groups.join(' ');
};

const verificationKey = (ownDeviceUid, peerDeviceUid) => `${ownDeviceUid}:${peerDeviceUid}`;

const canonicalDirectory = async (devices) => Promise.all((devices || []).map(async (device) => ({
	deviceUid: String(device.device_uid),
	fingerprint: await computeDeviceFingerprint(device),
})));

const directoryMap = (entries) => new Map((entries || []).map((entry) => [entry.deviceUid, entry.fingerprint]));

export const getPeerDeviceSecurity = async ({ ownAccountUid, peerAccountUid }) => {
	await ensureRegisteredDevice({ deviceLabel: navigator.userAgentData?.platform || navigator.platform || 'Browser' });
	const own = await getDeviceRegistrationPayload();
	const response = await CryptoService.accountDevices(peerAccountUid);
	const peerDevices = response.data?.devices || [];
	const currentDirectory = await canonicalDirectory(peerDevices);
	const currentMap = directoryMap(currentDirectory);
	let snapshot = await getRecord('accountSnapshots', String(peerAccountUid));
	const isFirstObservation = !snapshot;
	if (!snapshot) {
		snapshot = {
			accountUid: String(peerAccountUid),
			acknowledgedDirectory: currentDirectory,
			firstSeenAt: new Date().toISOString(),
			acknowledgedAt: new Date().toISOString(),
		};
		await putRecord('accountSnapshots', snapshot);
	}
	const acknowledgedMap = directoryMap(snapshot.acknowledgedDirectory);
	const added = currentDirectory.filter((entry) => !acknowledgedMap.has(entry.deviceUid));
	const removed = (snapshot.acknowledgedDirectory || []).filter((entry) => !currentMap.has(entry.deviceUid));
	const changed = currentDirectory.filter((entry) => {
		const known = acknowledgedMap.get(entry.deviceUid);
		return known && known !== entry.fingerprint;
	});

	const devices = [];
	for (const peer of peerDevices) {
		const fingerprint = await computeDeviceFingerprint(peer);
		const digest = await safetyDigest({ ownAccountUid, own, peerAccountUid, peer });
		const safetyNumber = formatSafetyNumber(digest);
		const key = verificationKey(own.device_uid, peer.device_uid);
		const verification = await getRecord('verifications', key);
		const verified = Boolean(
			verification
			&& verification.safetyNumber === safetyNumber
			&& verification.peerFingerprint === fingerprint
		);
		devices.push({
			deviceUid: String(peer.device_uid),
			fingerprint,
			safetyNumber,
			verified,
			verifiedAt: verified ? verification.verifiedAt : null,
			isNew: !isFirstObservation && added.some((entry) => entry.deviceUid === String(peer.device_uid)),
			identitySigningKey: peer.identity_signing_key,
			identityDhKey: peer.identity_dh_key,
		});
	}

	const directoryChanged = added.length > 0 || removed.length > 0 || changed.length > 0;
	const allVerified = devices.length > 0 && devices.every((device) => device.verified);
	return {
		peerAccountUid: String(peerAccountUid),
		ownDeviceUid: String(own.device_uid),
		status: directoryChanged ? 'changed' : (allVerified ? 'verified' : (devices.length ? 'unverified' : 'unavailable')),
		directoryChanged,
		added,
		removed,
		changed,
		devices,
	};
};

export const verifyPeerDevice = async ({ ownAccountUid, peerAccountUid, deviceUid }) => {
	const state = await getPeerDeviceSecurity({ ownAccountUid, peerAccountUid });
	const device = state.devices.find((item) => item.deviceUid === String(deviceUid));
	if (!device) throw new Error('e2ee_peer_device_not_found');
	await putRecord('verifications', {
		key: verificationKey(state.ownDeviceUid, device.deviceUid),
		ownDeviceUid: state.ownDeviceUid,
		peerAccountUid: String(peerAccountUid),
		peerDeviceUid: device.deviceUid,
		peerFingerprint: device.fingerprint,
		safetyNumber: device.safetyNumber,
		verifiedAt: new Date().toISOString(),
	});
	return getPeerDeviceSecurity({ ownAccountUid, peerAccountUid });
};

export const unverifyPeerDevice = async ({ ownAccountUid, peerAccountUid, deviceUid }) => {
	await ensureRegisteredDevice();
	const own = await getDeviceRegistrationPayload();
	await deleteRecord('verifications', verificationKey(own.device_uid, deviceUid));
	return getPeerDeviceSecurity({ ownAccountUid, peerAccountUid });
};

export const acknowledgePeerDirectory = async ({ ownAccountUid, peerAccountUid }) => {
	const response = await CryptoService.accountDevices(peerAccountUid);
	const currentDirectory = await canonicalDirectory(response.data?.devices || []);
	await putRecord('accountSnapshots', {
		accountUid: String(peerAccountUid),
		acknowledgedDirectory: currentDirectory,
		acknowledgedAt: new Date().toISOString(),
	});
	return getPeerDeviceSecurity({ ownAccountUid, peerAccountUid });
};

export const safetyNumberPayload = ({ ownAccountUid, peerAccountUid, ownDeviceUid, peerDeviceUid, safetyNumber }) => JSON.stringify({
	v: 'pubchat-safety-number-v1',
	accounts: [String(ownAccountUid), String(peerAccountUid)].sort(),
	devices: [String(ownDeviceUid), String(peerDeviceUid)].sort(),
	safety_number: String(safetyNumber).replace(/\s+/g, ''),
});
