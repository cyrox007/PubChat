const DB_NAME = 'pubchat-device-crypto-v1';
const DB_VERSION = 1;
const META_STORE = 'meta';
const KEY_STORE = 'keys';
const PREKEY_STORE = 'prekeys';
const DEVICE_META_KEY = 'device';
const SIGNED_PREKEY_DOMAIN = new TextEncoder().encode('pubchat-signed-prekey-v1\0');

const requireCrypto = () => {
	if (!window.isSecureContext || !globalThis.crypto?.subtle || !globalThis.indexedDB) {
		throw new Error('crypto_unsupported');
	}
	return globalThis.crypto.subtle;
};

const openDb = () => new Promise((resolve, reject) => {
	const request = indexedDB.open(DB_NAME, DB_VERSION);
	request.onupgradeneeded = () => {
		const db = request.result;
		if (!db.objectStoreNames.contains(META_STORE)) db.createObjectStore(META_STORE);
		if (!db.objectStoreNames.contains(KEY_STORE)) db.createObjectStore(KEY_STORE);
		if (!db.objectStoreNames.contains(PREKEY_STORE)) db.createObjectStore(PREKEY_STORE, { keyPath: 'id' });
	};
	request.onsuccess = () => resolve(request.result);
	request.onerror = () => reject(request.error || new Error('crypto_storage_unavailable'));
});

const transactionDone = (transaction) => new Promise((resolve, reject) => {
	transaction.oncomplete = () => resolve();
	transaction.onerror = () => reject(transaction.error || new Error('crypto_storage_failed'));
	transaction.onabort = () => reject(transaction.error || new Error('crypto_storage_aborted'));
});

const requestResult = (request) => new Promise((resolve, reject) => {
	request.onsuccess = () => resolve(request.result);
	request.onerror = () => reject(request.error || new Error('crypto_storage_failed'));
});

const getRecord = async (storeName, key) => {
	const db = await openDb();
	try {
		const tx = db.transaction(storeName, 'readonly');
		return await requestResult(tx.objectStore(storeName).get(key));
	} finally {
		db.close();
	}
};

const putRecords = async (entries) => {
	const db = await openDb();
	try {
		const stores = [...new Set(entries.map((entry) => entry.store))];
		const tx = db.transaction(stores, 'readwrite');
		for (const entry of entries) {
			const store = tx.objectStore(entry.store);
			if (entry.key === undefined) store.put(entry.value);
			else store.put(entry.value, entry.key);
		}
		await transactionDone(tx);
	} finally {
		db.close();
	}
};

const clearDb = async () => {
	const db = await openDb();
	try {
		const tx = db.transaction([META_STORE, KEY_STORE, PREKEY_STORE], 'readwrite');
		tx.objectStore(META_STORE).clear();
		tx.objectStore(KEY_STORE).clear();
		tx.objectStore(PREKEY_STORE).clear();
		await transactionDone(tx);
	} finally {
		db.close();
	}
};

const toBase64Url = (buffer) => {
	const bytes = new Uint8Array(buffer);
	let binary = '';
	for (const byte of bytes) binary += String.fromCharCode(byte);
	return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
};

const uint32Bytes = (value) => new Uint8Array([
	(value >>> 24) & 0xff,
	(value >>> 16) & 0xff,
	(value >>> 8) & 0xff,
	value & 0xff,
]);

const concatBytes = (...parts) => {
	const size = parts.reduce((total, part) => total + part.byteLength, 0);
	const result = new Uint8Array(size);
	let offset = 0;
	for (const part of parts) {
		const bytes = part instanceof Uint8Array ? part : new Uint8Array(part);
		result.set(bytes, offset);
		offset += bytes.byteLength;
	}
	return result;
};

const randomKeyId = () => {
	const value = new Uint32Array(1);
	crypto.getRandomValues(value);
	return value[0] & 0x7fffffff;
};

const generateStoredKeyPair = async (algorithm, privateUsages, publicUsages) => {
	const subtle = requireCrypto();
	const generated = await subtle.generateKey({ name: algorithm }, true, [...privateUsages, ...publicUsages]);
	const publicRaw = new Uint8Array(await subtle.exportKey('raw', generated.publicKey));
	const privatePkcs8 = new Uint8Array(await subtle.exportKey('pkcs8', generated.privateKey));
	try {
		const privateKey = await subtle.importKey(
			'pkcs8',
			privatePkcs8,
			{ name: algorithm },
			false,
			privateUsages,
		);
		return { privateKey, publicRaw };
	} finally {
		privatePkcs8.fill(0);
	}
};

const signPrekey = async (signingPrivateKey, prekeyId, publicRaw) => {
	const subtle = requireCrypto();
	const signed = concatBytes(SIGNED_PREKEY_DOMAIN, uint32Bytes(prekeyId), publicRaw);
	return new Uint8Array(await subtle.sign({ name: 'Ed25519' }, signingPrivateKey, signed));
};

const createSignedPrekey = async (signingPrivateKey) => {
	const id = randomKeyId();
	const pair = await generateStoredKeyPair('X25519', ['deriveBits'], []);
	const signature = await signPrekey(signingPrivateKey, id, pair.publicRaw);
	return {
		id,
		privateKey: pair.privateKey,
		publicKey: toBase64Url(pair.publicRaw),
		signature: toBase64Url(signature),
		createdAt: new Date().toISOString(),
	};
};

const createOneTimePrekeys = async (count, usedIds = new Set()) => {
	const amount = Math.max(0, Math.min(100, Number(count) || 0));
	const result = [];
	while (result.length < amount) {
		const id = randomKeyId();
		if (usedIds.has(id)) continue;
		usedIds.add(id);
		const pair = await generateStoredKeyPair('X25519', ['deriveBits'], []);
		result.push({
			id,
			privateKey: pair.privateKey,
			public_key: toBase64Url(pair.publicRaw),
			createdAt: new Date().toISOString(),
		});
	}
	return result;
};

const registrationPayload = async () => {
	const meta = await getRecord(META_STORE, DEVICE_META_KEY);
	const signingPublic = await getRecord(KEY_STORE, 'identity-signing-public');
	const dhPublic = await getRecord(KEY_STORE, 'identity-dh-public');
	const signedPrekey = await getRecord(KEY_STORE, 'signed-prekey-public');
	if (!meta || !signingPublic || !dhPublic || !signedPrekey) throw new Error('device_identity_missing');

	const db = await openDb();
	let oneTimePrekeys;
	try {
		const tx = db.transaction(PREKEY_STORE, 'readonly');
		const records = await requestResult(tx.objectStore(PREKEY_STORE).getAll());
		oneTimePrekeys = records
			.filter((item) => item.uploaded !== true)
			.map((item) => ({ id: item.id, public_key: item.public_key }));
	} finally {
		db.close();
	}

	return {
		device_uid: meta.deviceUid,
		device_label: meta.deviceLabel || null,
		key_version: 1,
		identity_signing_key: signingPublic,
		identity_dh_key: dhPublic,
		signed_prekey: {
			id: signedPrekey.id,
			public_key: signedPrekey.public_key,
			signature: signedPrekey.signature,
		},
		one_time_prekeys: oneTimePrekeys,
	};
};

export const ensureDeviceIdentity = async ({ deviceLabel = null, oneTimePrekeyCount = 20 } = {}) => {
	requireCrypto();
	const existing = await getRecord(META_STORE, DEVICE_META_KEY);
	if (existing) return registrationPayload();

	const signing = await generateStoredKeyPair('Ed25519', ['sign'], ['verify']);
	const dh = await generateStoredKeyPair('X25519', ['deriveBits'], []);
	const signedPrekey = await createSignedPrekey(signing.privateKey);
	const oneTime = await createOneTimePrekeys(oneTimePrekeyCount, new Set([signedPrekey.id]));
	const deviceUid = crypto.randomUUID();

	const entries = [
		{ store: META_STORE, key: DEVICE_META_KEY, value: { deviceUid, deviceLabel, createdAt: new Date().toISOString() } },
		{ store: KEY_STORE, key: 'identity-signing-private', value: signing.privateKey },
		{ store: KEY_STORE, key: 'identity-signing-public', value: toBase64Url(signing.publicRaw) },
		{ store: KEY_STORE, key: 'identity-dh-private', value: dh.privateKey },
		{ store: KEY_STORE, key: 'identity-dh-public', value: toBase64Url(dh.publicRaw) },
		{ store: KEY_STORE, key: 'signed-prekey-private', value: signedPrekey.privateKey },
		{ store: KEY_STORE, key: 'signed-prekey-public', value: { id: signedPrekey.id, public_key: signedPrekey.publicKey, signature: signedPrekey.signature, createdAt: signedPrekey.createdAt } },
		...oneTime.map((item) => ({ store: PREKEY_STORE, value: { ...item, uploaded: false } })),
	];
	await putRecords(entries);
	return registrationPayload();
};

export const markRegistrationUploaded = async (uploadedIds = []) => {
	const ids = new Set(uploadedIds.map((value) => Number(value)));
	if (!ids.size) return;
	const db = await openDb();
	try {
		const tx = db.transaction(PREKEY_STORE, 'readwrite');
		const store = tx.objectStore(PREKEY_STORE);
		for (const id of ids) {
			const record = await requestResult(store.get(id));
			if (record) store.put({ ...record, uploaded: true });
		}
		await transactionDone(tx);
	} finally {
		db.close();
	}
};

export const generateOneTimePrekeys = async (count = 20) => {
	requireCrypto();
	const db = await openDb();
	let existing;
	try {
		const tx = db.transaction(PREKEY_STORE, 'readonly');
		existing = await requestResult(tx.objectStore(PREKEY_STORE).getAllKeys());
	} finally {
		db.close();
	}
	const generated = await createOneTimePrekeys(count, new Set(existing.map(Number)));
	await putRecords(generated.map((item) => ({ store: PREKEY_STORE, value: { ...item, uploaded: false } })));
	return generated.map((item) => ({ id: item.id, public_key: item.public_key }));
};

export const rotateLocalSignedPrekey = async () => {
	requireCrypto();
	const signingPrivateKey = await getRecord(KEY_STORE, 'identity-signing-private');
	if (!signingPrivateKey) throw new Error('device_identity_missing');
	const signedPrekey = await createSignedPrekey(signingPrivateKey);
	await putRecords([
		{ store: KEY_STORE, key: 'signed-prekey-private', value: signedPrekey.privateKey },
		{ store: KEY_STORE, key: 'signed-prekey-public', value: { id: signedPrekey.id, public_key: signedPrekey.publicKey, signature: signedPrekey.signature, createdAt: signedPrekey.createdAt } },
	]);
	return { id: signedPrekey.id, public_key: signedPrekey.publicKey, signature: signedPrekey.signature };
};

export const verifySignedPrekey = async (deviceBundle) => {
	const subtle = requireCrypto();
	const fromBase64Url = (value) => {
		const padded = String(value).replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - String(value).length % 4) % 4);
		const binary = atob(padded);
		return Uint8Array.from(binary, (char) => char.charCodeAt(0));
	};
	const identityPublic = await subtle.importKey(
		'raw',
		fromBase64Url(deviceBundle.identity_signing_key),
		{ name: 'Ed25519' },
		false,
		['verify'],
	);
	const prekeyRaw = fromBase64Url(deviceBundle.signed_prekey.public_key);
	const signed = concatBytes(SIGNED_PREKEY_DOMAIN, uint32Bytes(deviceBundle.signed_prekey.id), prekeyRaw);
	return subtle.verify(
		{ name: 'Ed25519' },
		identityPublic,
		fromBase64Url(deviceBundle.signed_prekey.signature),
		signed,
	);
};

export const getDeviceRegistrationPayload = registrationPayload;

export const clearLocalDeviceIdentity = async () => {
	await clearDb();
};
