import CryptoService from '@/API/CryptoService';
import { ensureRegisteredDevice } from '@/crypto/deviceIdentitySync';
import { getDeviceRegistrationPayload, verifySignedPrekey } from '@/crypto/deviceIdentity';

const IDENTITY_DB = 'pubchat-device-crypto-v1';
const IDENTITY_DB_VERSION = 1;
const SESSION_DB = 'pubchat-e2ee-sessions-v1';
const SESSION_DB_VERSION = 1;
const SECURITY_STORE = 'pins';
const VERSION = 'pubchat-e2ee-v1';
const MAX_SKIP = 64;
const encoder = new TextEncoder();
const decoder = new TextDecoder();

const openDb = (name, version, upgrade) => new Promise((resolve, reject) => {
	const request = indexedDB.open(name, version);
	request.onupgradeneeded = () => upgrade?.(request.result);
	request.onsuccess = () => resolve(request.result);
	request.onerror = () => reject(request.error || new Error('e2ee_storage_unavailable'));
});

const openIdentityDb = () => openDb(IDENTITY_DB, IDENTITY_DB_VERSION);
const openSessionDb = () => openDb(SESSION_DB, SESSION_DB_VERSION, (db) => {
	if (!db.objectStoreNames.contains('sessions')) db.createObjectStore('sessions', { keyPath: 'key' });
	if (!db.objectStoreNames.contains('messageKeys')) db.createObjectStore('messageKeys', { keyPath: 'key' });
	if (!db.objectStoreNames.contains(SECURITY_STORE)) db.createObjectStore(SECURITY_STORE, { keyPath: 'deviceUid' });
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

const readIdentity = async (storeName, key) => {
	const db = await openIdentityDb();
	try {
		return await requestResult(db.transaction(storeName, 'readonly').objectStore(storeName).get(key));
	} finally {
		db.close();
	}
};

const deleteIdentityPrekey = async (id) => {
	if (id === null || id === undefined) return;
	const db = await openIdentityDb();
	try {
		const tx = db.transaction('prekeys', 'readwrite');
		tx.objectStore('prekeys').delete(Number(id));
		await txDone(tx);
	} finally {
		db.close();
	}
};

const sessionGet = async (key) => {
	const db = await openSessionDb();
	try {
		return await requestResult(db.transaction('sessions', 'readonly').objectStore('sessions').get(key));
	} finally {
		db.close();
	}
};

const sessionPut = async (record) => {
	const db = await openSessionDb();
	try {
		const tx = db.transaction('sessions', 'readwrite');
		tx.objectStore('sessions').put(record);
		await txDone(tx);
	} finally {
		db.close();
	}
};

const sessionDelete = async (key) => {
	const db = await openSessionDb();
	try {
		const tx = db.transaction('sessions', 'readwrite');
		tx.objectStore('sessions').delete(key);
		await txDone(tx);
	} finally {
		db.close();
	}
};

const messageKeyGet = async (key) => {
	const db = await openSessionDb();
	try {
		return await requestResult(db.transaction('messageKeys', 'readonly').objectStore('messageKeys').get(key));
	} finally {
		db.close();
	}
};

const messageKeyPut = async (record) => {
	const db = await openSessionDb();
	try {
		const tx = db.transaction('messageKeys', 'readwrite');
		tx.objectStore('messageKeys').put(record);
		await txDone(tx);
	} finally {
		db.close();
	}
};

const securityRecordGet = async (key) => {
	const db = await openSessionDb();
	try {
		return await requestResult(db.transaction(SECURITY_STORE, 'readonly').objectStore(SECURITY_STORE).get(key));
	} finally {
		db.close();
	}
};

const securityRecordPut = async (record) => {
	const db = await openSessionDb();
	try {
		const tx = db.transaction(SECURITY_STORE, 'readwrite');
		tx.objectStore(SECURITY_STORE).put(record);
		await txDone(tx);
	} finally {
		db.close();
	}
};

const pinDevice = async (deviceUid, identityDh, identitySigning) => {
	const db = await openSessionDb();
	try {
		const tx = db.transaction(SECURITY_STORE, 'readwrite');
		const store = tx.objectStore(SECURITY_STORE);
		const existing = await requestResult(store.get(deviceUid));
		if (existing && (existing.identityDh !== identityDh || existing.identitySigning !== identitySigning)) {
			tx.abort();
			throw new Error('e2ee_identity_changed');
		}
		if (!existing) store.put({ deviceUid, identityDh, identitySigning, firstSeenAt: new Date().toISOString() });
		await txDone(tx);
	} finally {
		db.close();
	}
};

const b64 = (buffer) => {
	const bytes = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer);
	let binary = '';
	for (const byte of bytes) binary += String.fromCharCode(byte);
	return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
};

const unb64 = (value) => {
	const normalized = String(value || '');
	const padded = normalized.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - normalized.length % 4) % 4);
	const binary = atob(padded);
	return Uint8Array.from(binary, (char) => char.charCodeAt(0));
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

const importX25519Public = (value) => crypto.subtle.importKey('raw', unb64(value), { name: 'X25519' }, false, []);

const deriveX25519 = async (privateKey, publicValue) => {
	const publicKey = await importX25519Public(publicValue);
	return new Uint8Array(await crypto.subtle.deriveBits({ name: 'X25519', public: publicKey }, privateKey, 256));
};

const rootToChain = async (parts) => {
	const material = concat(...parts);
	try {
		const hkdf = await crypto.subtle.importKey('raw', material, 'HKDF', false, ['deriveBits']);
		const raw = new Uint8Array(await crypto.subtle.deriveBits(
			{ name: 'HKDF', hash: 'SHA-256', salt: new Uint8Array(32), info: encoder.encode('pubchat-e2ee-root-v1') },
			hkdf,
			256,
		));
		try {
			return await crypto.subtle.importKey('raw', raw, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
		} finally {
			raw.fill(0);
		}
	} finally {
		material.fill(0);
		parts.forEach((part) => part.fill?.(0));
	}
};

const ratchetStep = async (chainKey, counter) => {
	const messageRaw = new Uint8Array(await crypto.subtle.sign('HMAC', chainKey, encoder.encode(`pubchat-message-key-v1:${counter}`)));
	const nextRaw = new Uint8Array(await crypto.subtle.sign('HMAC', chainKey, encoder.encode(`pubchat-chain-key-v1:${counter}`)));
	try {
		const messageKey = await crypto.subtle.importKey('raw', messageRaw, { name: 'AES-GCM' }, false, ['encrypt', 'decrypt']);
		const nextChainKey = await crypto.subtle.importKey('raw', nextRaw, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
		return { messageKey, nextChainKey };
	} finally {
		messageRaw.fill(0);
		nextRaw.fill(0);
	}
};

const aad = ({ senderDeviceUid, recipientDeviceUid, sessionId, counter }) => encoder.encode(JSON.stringify({
	v: VERSION,
	s: senderDeviceUid,
	r: recipientDeviceUid,
	sid: sessionId,
	c: counter,
}));

const outboundKey = (targetDeviceUid) => `out:${targetDeviceUid}`;
const inboundKey = (senderDeviceUid, sessionId) => `in:${senderDeviceUid}:${sessionId}`;
const cachedMessageKey = (direction, sessionId, counter) => `${direction}:${sessionId}:${counter}`;

const createOutboundSession = async (target, registration) => {
	if (!(await verifySignedPrekey(target))) throw new Error('e2ee_invalid_target_signed_prekey');
	await pinDevice(target.device_uid, target.identity_dh_key, target.identity_signing_key);
	const identityPrivate = await readIdentity('keys', 'identity-dh-private');
	if (!identityPrivate) throw new Error('device_identity_missing');

	const ephemeral = await crypto.subtle.generateKey({ name: 'X25519' }, true, ['deriveBits']);
	const ephemeralPublic = new Uint8Array(await crypto.subtle.exportKey('raw', ephemeral.publicKey));
	const dh1 = await deriveX25519(identityPrivate, target.signed_prekey.public_key);
	const dh2 = await deriveX25519(ephemeral.privateKey, target.identity_dh_key);
	const dh3 = await deriveX25519(ephemeral.privateKey, target.signed_prekey.public_key);
	const parts = [dh1, dh2, dh3];
	if (target.one_time_prekey?.public_key) parts.push(await deriveX25519(ephemeral.privateKey, target.one_time_prekey.public_key));
	const chainKey = await rootToChain(parts);
	const sessionId = crypto.randomUUID();
	const record = {
		key: outboundKey(target.device_uid),
		direction: 'out',
		sessionId,
		peerDeviceUid: target.device_uid,
		peerIdentityDh: target.identity_dh_key,
		chainKey,
		nextCounter: 0,
		headerSent: false,
		initialHeader: {
			ephemeral_key: b64(ephemeralPublic),
			target_signed_prekey_id: target.signed_prekey.id,
			target_one_time_prekey_id: target.one_time_prekey?.id ?? null,
			sender_identity_dh_key: registration.identity_dh_key,
			sender_identity_signing_key: registration.identity_signing_key,
		},
		createdAt: new Date().toISOString(),
	};
	await sessionPut(record);
	return { record, created: true };
};

const getOrCreateOutbound = async (target, registration) => {
	const existing = await sessionGet(outboundKey(target.device_uid));
	if (existing) {
		if (existing.peerIdentityDh && existing.peerIdentityDh !== target.identity_dh_key) throw new Error('e2ee_identity_changed');
		return { record: existing, created: false };
	}
	return createOutboundSession(target, registration);
};

const encryptForSession = async (session, senderDeviceUid, recipientDeviceUid, payload) => {
	const counter = session.nextCounter;
	const { messageKey, nextChainKey } = await ratchetStep(session.chainKey, counter);
	const nonce = crypto.getRandomValues(new Uint8Array(12));
	const associatedData = aad({ senderDeviceUid, recipientDeviceUid, sessionId: session.sessionId, counter });
	const ciphertext = await crypto.subtle.encrypt(
		{ name: 'AES-GCM', iv: nonce, additionalData: associatedData, tagLength: 128 },
		messageKey,
		encoder.encode(JSON.stringify(payload)),
	);
	await messageKeyPut({
		key: cachedMessageKey('out', session.sessionId, counter),
		messageKey,
		createdAt: new Date().toISOString(),
	});
	const updated = { ...session, chainKey: nextChainKey, nextCounter: counter + 1 };
	await sessionPut(updated);
	return {
		recipient_device_uid: recipientDeviceUid,
		session_id: session.sessionId,
		counter,
		nonce: b64(nonce),
		ciphertext: b64(ciphertext),
		initial_header: session.headerSent ? null : session.initialHeader,
	};
};

const activeOwnDevices = async () => {
	const response = await CryptoService.devices();
	return (response.data?.devices || []).filter((item) => !item.revoked_at);
};

const peerDirectory = async (accountUid) => {
	const response = await CryptoService.accountDevices(accountUid);
	return response.data?.devices || [];
};

const deviceFingerprint = async (device) => b64(await crypto.subtle.digest('SHA-256', concat(
	encoder.encode('pubchat-device-identity-v1\0'),
	unb64(device.identity_signing_key),
	unb64(device.identity_dh_key),
)));

const canonicalPeerDirectory = async (devices) => Promise.all((devices || []).map(async (device) => ({
	deviceUid: String(device.device_uid),
	fingerprint: await deviceFingerprint(device),
})));

const sameDirectory = (left, right) => {
	const a = new Map((left || []).map((item) => [String(item.deviceUid), String(item.fingerprint)]));
	const b = new Map((right || []).map((item) => [String(item.deviceUid), String(item.fingerprint)]));
	if (a.size !== b.size) return false;
	for (const [deviceUid, fingerprint] of a.entries()) {
		if (b.get(deviceUid) !== fingerprint) return false;
	}
	return true;
};

const assertPeerDirectoryAcknowledged = async (accountUid, peers) => {
	const key = `snapshot:${accountUid}`;
	const currentDirectory = await canonicalPeerDirectory(peers);
	const snapshot = await securityRecordGet(key);
	if (!snapshot) {
		await securityRecordPut({
			deviceUid: key,
			recordType: 'account-snapshot',
			accountUid: String(accountUid),
			acknowledgedDirectory: currentDirectory,
			firstSeenAt: new Date().toISOString(),
			acknowledgedAt: new Date().toISOString(),
		});
		return;
	}
	if (sameDirectory(snapshot.acknowledgedDirectory, currentDirectory)) return;
	window.dispatchEvent(new CustomEvent('pubchat:conversation-encryption-refresh', {
		detail: { peerUid: String(accountUid), reason: 'peer_device_directory_changed' },
	}));
	const error = new Error('e2ee_peer_directory_unacknowledged');
	error.code = 'e2ee_peer_directory_unacknowledged';
	throw error;
};

const claimPeerBundles = async (accountUid) => {
	const response = await CryptoService.prekeyBundle(accountUid);
	return response.data?.bundle?.devices || [];
};

const buildTargets = async (receiverUid, peerDevices = null) => {
	const own = await activeOwnDevices();
	const peers = peerDevices || await peerDirectory(receiverUid);
	if (!peers.length) return { own, peers, claimed: new Map() };
	const missingPeer = [];
	for (const device of peers) {
		if (!(await sessionGet(outboundKey(device.device_uid)))) missingPeer.push(device.device_uid);
	}
	const peerByUid = new Map(peers.map((item) => [String(item.device_uid), item]));
	let claimed = new Map();
	if (missingPeer.length) {
		const bundles = await claimPeerBundles(receiverUid);
		for (const item of bundles) {
			const directoryDevice = peerByUid.get(String(item.device_uid));
			if (!directoryDevice || !missingPeer.includes(item.device_uid)) continue;
			if (directoryDevice.identity_dh_key !== item.identity_dh_key || directoryDevice.identity_signing_key !== item.identity_signing_key) {
				throw new Error('e2ee_peer_directory_changed_during_send');
			}
			claimed.set(item.device_uid, item);
		}
	}
	return { own, peers, claimed };
};

export const hasPeerCryptoDevices = async (accountUid) => (await peerDirectory(accountUid)).length > 0;

export const sendEncryptedPayload = async ({ receiverUid, payload, frontId, attachmentUid = null, deviceLabel = null }) => {
	await ensureRegisteredDevice({ deviceLabel, oneTimePrekeyCount: 20 });
	const registration = await getDeviceRegistrationPayload();
	const peers = await peerDirectory(receiverUid);
	await assertPeerDirectoryAcknowledged(receiverUid, peers);
	const { own, claimed } = await buildTargets(receiverUid, peers);
	if (!peers.length) return { encrypted: false, reason: 'peer_no_crypto_devices' };

	const targets = [
		...own.map((item) => ({ ...item, accountScope: 'self' })),
		...peers.map((item) => ({ ...(claimed.get(item.device_uid) || item), accountScope: 'peer' })),
	];
	const createdKeys = [];
	const touchedSessions = [];
	try {
		const envelopes = [];
		for (const target of targets) {
			const resolved = await getOrCreateOutbound(target, registration);
			if (resolved.created) createdKeys.push(resolved.record.key);
			touchedSessions.push(resolved.record.key);
			envelopes.push(await encryptForSession(resolved.record, registration.device_uid, target.device_uid, payload));
		}
		const response = await CryptoService.sendEncryptedMessage({
			receiver_uid: receiverUid,
			sender_device_uid: registration.device_uid,
			front_id: frontId,
			envelopes,
			attachment_uid: attachmentUid,
		});
		for (const key of touchedSessions) {
			const session = await sessionGet(key);
			if (session && !session.headerSent) await sessionPut({ ...session, headerSent: true });
		}
		return { encrypted: true, response: response.data };
	} catch (error) {
		for (const key of createdKeys) await sessionDelete(key);
		throw error;
	}
};

export const sendEncryptedText = ({ receiverUid, text, frontId, deviceLabel = null }) => sendEncryptedPayload({
	receiverUid,
	frontId,
	deviceLabel,
	payload: { type: 'text', text },
});

const loadSignedPrekeyPrivate = async (signedPrekeyId) => {
	const archived = await readIdentity('keys', `signed-prekey-private:${signedPrekeyId}`);
	if (archived) return archived;
	const currentPublic = await readIdentity('keys', 'signed-prekey-public');
	if (Number(currentPublic?.id) !== Number(signedPrekeyId)) throw new Error('e2ee_signed_prekey_unavailable');
	const current = await readIdentity('keys', 'signed-prekey-private');
	if (!current) throw new Error('e2ee_signed_prekey_unavailable');
	return current;
};

const createInboundSession = async (envelope) => {
	const header = envelope.initial_header;
	if (!header) throw new Error('e2ee_missing_initial_header');
	await pinDevice(envelope.sender_device_uid, header.sender_identity_dh_key, header.sender_identity_signing_key);
	const identityPrivate = await readIdentity('keys', 'identity-dh-private');
	const signedPrekeyPrivate = await loadSignedPrekeyPrivate(header.target_signed_prekey_id);
	if (!identityPrivate || !signedPrekeyPrivate) throw new Error('device_identity_missing');
	const dh1 = await deriveX25519(signedPrekeyPrivate, header.sender_identity_dh_key);
	const dh2 = await deriveX25519(identityPrivate, header.ephemeral_key);
	const dh3 = await deriveX25519(signedPrekeyPrivate, header.ephemeral_key);
	const parts = [dh1, dh2, dh3];
	let oneTimeRecord = null;
	if (header.target_one_time_prekey_id !== null && header.target_one_time_prekey_id !== undefined) {
		oneTimeRecord = await readIdentity('prekeys', Number(header.target_one_time_prekey_id));
		if (!oneTimeRecord?.privateKey) throw new Error('e2ee_one_time_prekey_unavailable');
		parts.push(await deriveX25519(oneTimeRecord.privateKey, header.ephemeral_key));
	}
	const chainKey = await rootToChain(parts);
	const record = {
		key: inboundKey(envelope.sender_device_uid, envelope.session_id),
		direction: 'in',
		sessionId: envelope.session_id,
		peerDeviceUid: envelope.sender_device_uid,
		chainKey,
		nextCounter: 0,
		createdAt: new Date().toISOString(),
	};
	await sessionPut(record);
	return { record, consumedOneTimePrekeyId: oneTimeRecord?.id ?? null };
};

const decryptWithCachedKey = async (messageKey, envelope) => {
	const registration = await getDeviceRegistrationPayload();
	const associatedData = aad({
		senderDeviceUid: envelope.sender_device_uid,
		recipientDeviceUid: registration.device_uid,
		sessionId: envelope.session_id,
		counter: envelope.counter,
	});
	const plaintext = await crypto.subtle.decrypt(
		{ name: 'AES-GCM', iv: unb64(envelope.nonce), additionalData: associatedData, tagLength: 128 },
		messageKey,
		unb64(envelope.ciphertext),
	);
	const payload = JSON.parse(decoder.decode(plaintext));
	if (!payload || !['text', 'attachment'].includes(payload.type)) throw new Error('e2ee_invalid_plaintext');
	if (payload.type === 'text' && typeof payload.text !== 'string') throw new Error('e2ee_invalid_plaintext');
	if (payload.type === 'attachment' && (!payload.attachment?.uid || !payload.attachment?.key || !payload.attachment?.nonce)) {
		throw new Error('e2ee_invalid_attachment_payload');
	}
	return payload;
};

const decryptInbound = async (envelope) => {
	const cacheKey = cachedMessageKey('in', envelope.session_id, envelope.counter);
	const cached = await messageKeyGet(cacheKey);
	if (cached?.messageKey) return decryptWithCachedKey(cached.messageKey, envelope);

	let session = await sessionGet(inboundKey(envelope.sender_device_uid, envelope.session_id));
	let consumedOneTimePrekeyId = null;
	if (!session) {
		const created = await createInboundSession(envelope);
		session = created.record;
		consumedOneTimePrekeyId = created.consumedOneTimePrekeyId;
	}
	if (envelope.counter < session.nextCounter) throw new Error('e2ee_message_key_expired');
	if (envelope.counter - session.nextCounter > MAX_SKIP) throw new Error('e2ee_counter_gap_too_large');

	let current = session;
	let targetKey = null;
	for (let counter = current.nextCounter; counter <= envelope.counter; counter += 1) {
		const step = await ratchetStep(current.chainKey, counter);
		await messageKeyPut({
			key: cachedMessageKey('in', current.sessionId, counter),
			messageKey: step.messageKey,
			createdAt: new Date().toISOString(),
		});
		if (counter === envelope.counter) targetKey = step.messageKey;
		current = { ...current, chainKey: step.nextChainKey, nextCounter: counter + 1 };
	}
	await sessionPut(current);
	const payload = await decryptWithCachedKey(targetKey, envelope);
	if (consumedOneTimePrekeyId !== null) await deleteIdentityPrekey(consumedOneTimePrekeyId);
	return payload;
};

const decryptOwnOutbound = async (envelope) => {
	const cached = await messageKeyGet(cachedMessageKey('out', envelope.session_id, envelope.counter));
	if (!cached?.messageKey) throw new Error('e2ee_sent_history_key_unavailable');
	return decryptWithCachedKey(cached.messageKey, envelope);
};

const projectDecryptedPayload = (message, payload) => {
	if (payload.type === 'text') {
		return { ...message, content: payload.text, encrypted: true, encryption_version: VERSION, e2ee_locked: false };
	}
	const attachment = payload.attachment;
	const kind = ['image', 'video', 'audio', 'voice', 'file'].includes(attachment.kind) ? attachment.kind : 'file';
	const privateFile = {
		url: '',
		name: attachment.name || 'Файл',
		type: attachment.mime_type || 'application/octet-stream',
		size: Number(attachment.size) || 0,
		duration: Number(attachment.duration) || 0,
		waveform: Array.isArray(attachment.waveform) ? attachment.waveform : [],
		encrypted_attachment: attachment,
	};
	return {
		...message,
		content_type: kind,
		content: typeof payload.caption === 'string' ? payload.caption : '',
		media_metadata: {
			files: [privateFile],
			duration: privateFile.duration,
			waveform: privateFile.waveform,
			voice: kind === 'voice' ? '' : undefined,
			transcription: { status: 'none', text: '' },
			encrypted_attachment: true,
		},
		encrypted: true,
		encryption_version: VERSION,
		e2ee_locked: false,
	};
};

export const decryptMessageForCurrentDevice = async (message) => {
	if (message?.content_type !== 'e2ee') return message;
	const registration = await getDeviceRegistrationPayload();
	const envelope = (message.envelopes || []).find((item) => item.recipient_device_uid === registration.device_uid);
	if (!envelope) return { ...message, content: 'Сообщение зашифровано для другого устройства', e2ee_locked: true };
	try {
		const payload = envelope.sender_device_uid === registration.device_uid
			? await decryptOwnOutbound(envelope)
			: await decryptInbound(envelope);
		return projectDecryptedPayload(message, payload);
	} catch (error) {
		console.warn('Не удалось расшифровать Messenger envelope', error);
		return { ...message, content: 'Не удалось расшифровать сообщение на этом устройстве', encrypted: true, e2ee_locked: true };
	}
};

export const hydrateConversationEnvelopes = async (messages) => {
	const encrypted = (messages || []).filter((item) => item.content_type === 'e2ee' && item.uid);
	if (!encrypted.length) return messages || [];
	const response = await CryptoService.messageEnvelopes(encrypted.map((item) => item.uid));
	const mapping = response.data?.envelopes || {};
	return Promise.all((messages || []).map(async (message) => {
		if (message.content_type !== 'e2ee') return message;
		return decryptMessageForCurrentDevice({ ...message, envelopes: mapping[message.uid] || [] });
	}));
};

export const resetOutboundSessionForDevice = async (deviceUid) => sessionDelete(outboundKey(deviceUid));
