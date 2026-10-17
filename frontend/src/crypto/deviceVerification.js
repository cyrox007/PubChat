import CryptoService from '@/API/CryptoService';
import { ensureRegisteredDevice } from '@/crypto/deviceIdentitySync';
import { getDeviceRegistrationPayload } from '@/crypto/deviceIdentity';

const DB_NAME = 'pubchat-e2ee-sessions-v1';
const DB_VERSION = 1;
const SECURITY_STORE = 'pins';
const encoder = new TextEncoder();

const openDb = () => new Promise((resolve, reject) => {
	const request = indexedDB.open(DB_NAME, DB_VERSION);
	request.onupgradeneeded = () => {
		const db = request.result;
		if (!db.objectStoreNames.contains('sessions')) db.createObjectStore('sessions', { keyPath: 'key' });
		if (!db.objectStoreNames.contains('messageKeys')) db.createObjectStore('messageKeys', { keyPath: 'key' });
		if (!db.objectStoreNames.contains(SECURITY_STORE)) db.createObjectStore(SECURITY_STORE, { keyPath: 'deviceUid' });
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
const getRecord = async (key) => {
	const db = await openDb();
	try { return await requestResult(db.transaction(SECURITY_STORE, 'readonly').objectStore(SECURITY_STORE).get(key)); }
	finally { db.close(); }
};
const putRecord = async (value) => {
	const db = await openDb();
	try { const tx = db.transaction(SECURITY_STORE, 'readwrite'); tx.objectStore(SECURITY_STORE).put(value); await txDone(tx); }
	finally { db.close(); }
};
const deleteRecord = async (key) => {
	const db = await openDb();
	try { const tx = db.transaction(SECURITY_STORE, 'readwrite'); tx.objectStore(SECURITY_STORE).delete(key); await txDone(tx); }
	finally { db.close(); }
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
	for (const part of arrays) { out.set(part, offset); offset += part.byteLength; }
	return out;
};
const descriptor = ({ accountUid, deviceUid, identitySigningKey, identityDhKey }) => ({
	account_uid: String(accountUid), device_uid: String(deviceUid), identity_signing_key: String(identitySigningKey), identity_dh_key: String(identityDhKey),
});
const fingerprint = async (device) => toBase64Url(await crypto.subtle.digest('SHA-256', concat(
	encoder.encode('pubchat-device-identity-v1\0'), fromBase64Url(device.identity_signing_key), fromBase64Url(device.identity_dh_key),
)));
const safetyDigest = async ({ ownAccountUid, own, peerAccountUid, peer }) => {
	const entries = [
		descriptor({ accountUid: ownAccountUid, deviceUid: own.device_uid, identitySigningKey: own.identity_signing_key, identityDhKey: own.identity_dh_key }),
		descriptor({ accountUid: peerAccountUid, deviceUid: peer.device_uid, identitySigningKey: peer.identity_signing_key, identityDhKey: peer.identity_dh_key }),
	].sort((a, b) => `${a.account_uid}:${a.device_uid}`.localeCompare(`${b.account_uid}:${b.device_uid}`));
	return new Uint8Array(await crypto.subtle.digest('SHA-256', concat(
		encoder.encode('pubchat-safety-number-v1\0'), encoder.encode(JSON.stringify(entries[0])), encoder.encode('\0'), encoder.encode(JSON.stringify(entries[1])),
	)));
};
const formatSafetyNumber = (digest) => {
	const view = new DataView(digest.buffer, digest.byteOffset, digest.byteLength);
	const groups = [];
	for (let offset = 0; offset < digest.byteLength; offset += 4) groups.push(String(view.getUint32(offset, false) % 100000).padStart(5, '0'));
	return groups.join(' ');
};
const verificationKey = (ownDeviceUid, peerDeviceUid) => `verify:${ownDeviceUid}:${peerDeviceUid}`;
const snapshotKey = (peerAccountUid) => `snapshot:${peerAccountUid}`;
const canonicalDirectory = async (devices) => Promise.all((devices || []).map(async (device) => ({ deviceUid: String(device.device_uid), fingerprint: await fingerprint(device) })));
const directoryMap = (entries) => new Map((entries || []).map((entry) => [entry.deviceUid, entry.fingerprint]));

export const getPeerDeviceSecurity = async ({ ownAccountUid, peerAccountUid }) => {
	await ensureRegisteredDevice({ deviceLabel: navigator.userAgentData?.platform || navigator.platform || 'Browser' });
	const own = await getDeviceRegistrationPayload();
	// CryptoService.accountDevices is the common fail-closed transparency boundary.
	const response = await CryptoService.accountDevices(peerAccountUid);
	const peerDevices = response.data?.devices || [];
	const currentDirectory = await canonicalDirectory(peerDevices);
	const currentMap = directoryMap(currentDirectory);
	const key = snapshotKey(peerAccountUid);
	let snapshot = await getRecord(key);
	const firstObservation = !snapshot;
	if (!snapshot) {
		snapshot = { deviceUid: key, recordType: 'account-snapshot', accountUid: String(peerAccountUid), acknowledgedDirectory: currentDirectory, firstSeenAt: new Date().toISOString(), acknowledgedAt: new Date().toISOString() };
		await putRecord(snapshot);
	}
	const acknowledgedMap = directoryMap(snapshot.acknowledgedDirectory);
	const added = currentDirectory.filter((entry) => !acknowledgedMap.has(entry.deviceUid));
	const removed = (snapshot.acknowledgedDirectory || []).filter((entry) => !currentMap.has(entry.deviceUid));
	const changed = currentDirectory.filter((entry) => acknowledgedMap.has(entry.deviceUid) && acknowledgedMap.get(entry.deviceUid) !== entry.fingerprint);
	const devices = [];
	for (const peer of peerDevices) {
		const peerFingerprint = await fingerprint(peer);
		const number = formatSafetyNumber(await safetyDigest({ ownAccountUid, own, peerAccountUid, peer }));
		const stored = await getRecord(verificationKey(own.device_uid, peer.device_uid));
		const verified = Boolean(stored && stored.safetyNumber === number && stored.peerFingerprint === peerFingerprint);
		devices.push({
			deviceUid: String(peer.device_uid), fingerprint: peerFingerprint, safetyNumber: number, verified,
			verifiedAt: verified ? stored.verifiedAt : null,
			isNew: !firstObservation && added.some((entry) => entry.deviceUid === String(peer.device_uid)),
		});
	}
	const directoryChanged = added.length > 0 || removed.length > 0 || changed.length > 0;
	const allVerified = devices.length > 0 && devices.every((device) => device.verified);
	return {
		peerAccountUid: String(peerAccountUid),
		ownDeviceUid: String(own.device_uid),
		status: directoryChanged ? 'changed' : (allVerified ? 'verified' : (devices.length ? 'unverified' : 'unavailable')),
		directoryChanged,
		directoryCheckpoint: response.data?.directory_checkpoint || null,
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
	await putRecord({ deviceUid: verificationKey(state.ownDeviceUid, device.deviceUid), recordType: 'verification', ownDeviceUid: state.ownDeviceUid, peerAccountUid: String(peerAccountUid), peerDeviceUid: device.deviceUid, peerFingerprint: device.fingerprint, safetyNumber: device.safetyNumber, verifiedAt: new Date().toISOString() });
	return getPeerDeviceSecurity({ ownAccountUid, peerAccountUid });
};
export const unverifyPeerDevice = async ({ ownAccountUid, peerAccountUid, deviceUid }) => {
	await ensureRegisteredDevice();
	const own = await getDeviceRegistrationPayload();
	await deleteRecord(verificationKey(own.device_uid, deviceUid));
	return getPeerDeviceSecurity({ ownAccountUid, peerAccountUid });
};
export const acknowledgePeerDirectory = async ({ ownAccountUid, peerAccountUid }) => {
	const response = await CryptoService.accountDevices(peerAccountUid);
	const currentDirectory = await canonicalDirectory(response.data?.devices || []);
	const key = snapshotKey(peerAccountUid);
	await putRecord({ deviceUid: key, recordType: 'account-snapshot', accountUid: String(peerAccountUid), acknowledgedDirectory: currentDirectory, acknowledgedAt: new Date().toISOString() });
	return getPeerDeviceSecurity({ ownAccountUid, peerAccountUid });
};
export const safetyNumberPayload = ({ ownAccountUid, peerAccountUid, ownDeviceUid, peerDeviceUid, safetyNumber }) => JSON.stringify({
	v: 'pubchat-safety-number-v1', accounts: [String(ownAccountUid), String(peerAccountUid)].sort(), devices: [String(ownDeviceUid), String(peerDeviceUid)].sort(), safety_number: String(safetyNumber).replace(/\s+/g, ''),
});
