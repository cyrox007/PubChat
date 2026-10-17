import CryptoService from '@/API/CryptoService';

const DB_NAME = 'pubchat-e2ee-sessions-v1';
const DB_VERSION = 1;
const STORE = 'pins';
const VERSION = 'pubchat-device-directory-v1';
const MAX_HISTORY_GAP = 1000;

const openDb = () => new Promise((resolve, reject) => {
	const request = indexedDB.open(DB_NAME, DB_VERSION);
	request.onupgradeneeded = () => {
		const db = request.result;
		if (!db.objectStoreNames.contains('sessions')) db.createObjectStore('sessions', { keyPath: 'key' });
		if (!db.objectStoreNames.contains('messageKeys')) db.createObjectStore('messageKeys', { keyPath: 'key' });
		if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE, { keyPath: 'deviceUid' });
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
const keyFor = (accountUid) => `checkpoint:${accountUid}`;
const readRecord = async (key) => {
	const db = await openDb();
	try { return await requestResult(db.transaction(STORE, 'readonly').objectStore(STORE).get(key)); }
	finally { db.close(); }
};
const writeRecord = async (record) => {
	const db = await openDb();
	try { const tx = db.transaction(STORE, 'readwrite'); tx.objectStore(STORE).put(record); await txDone(tx); }
	finally { db.close(); }
};

const normalizedCheckpoint = (checkpoint) => {
	if (!checkpoint || checkpoint.version !== VERSION) return null;
	const sequence = Number(checkpoint.sequence);
	const eventHash = String(checkpoint.event_hash || '');
	const previousHash = String(checkpoint.previous_hash || '');
	const directoryHash = String(checkpoint.directory_hash || '');
	if (!Number.isSafeInteger(sequence) || sequence < 1) return null;
	if (!/^[0-9a-f]{64}$/.test(eventHash) || !/^[0-9a-f]{64}$/.test(previousHash) || !/^[0-9a-f]{64}$/.test(directoryHash)) return null;
	return { version: VERSION, sequence, eventHash, previousHash, directoryHash };
};

const conflict = (reason, stored, current) => ({ ok: false, reason, stored, current });

const verifyForwardChain = async ({ accountUid, stored, current }) => {
	const gap = current.sequence - stored.sequence;
	if (gap > MAX_HISTORY_GAP) return conflict('history_gap_too_large', stored, current);
	let cursor = stored.sequence;
	let expectedPrevious = stored.eventHash;
	while (cursor < current.sequence) {
		const response = await CryptoService.directoryHistory(accountUid, cursor, Math.min(200, current.sequence - cursor));
		const events = response.data?.events || [];
		if (!events.length) return conflict('history_incomplete', stored, current);
		for (const event of events) {
			const sequence = Number(event.sequence);
			const eventHash = String(event.event_hash || '');
			const previousHash = String(event.previous_hash || '');
			const directoryHash = String(event.directory_hash || '');
			if (sequence !== cursor + 1) return conflict('history_sequence_gap', stored, current);
			if (previousHash !== expectedPrevious) return conflict('history_hash_chain_broken', stored, current);
			if (!/^[0-9a-f]{64}$/.test(eventHash) || !/^[0-9a-f]{64}$/.test(directoryHash)) return conflict('history_invalid_hash', stored, current);
			cursor = sequence;
			expectedPrevious = eventHash;
			if (cursor >= current.sequence) break;
		}
	}
	if (cursor !== current.sequence || expectedPrevious !== current.eventHash) return conflict('checkpoint_not_in_history', stored, current);
	return { ok: true };
};

export const observeDirectoryCheckpoint = async ({ accountUid, checkpoint, requireCheckpoint = true }) => {
	const current = normalizedCheckpoint(checkpoint);
	if (!current) {
		if (!requireCheckpoint && !checkpoint) return { ok: true, firstObservation: false, checkpoint: null };
		return conflict('checkpoint_missing_or_invalid', null, checkpoint || null);
	}
	const key = keyFor(accountUid);
	const storedRecord = await readRecord(key);
	const stored = storedRecord ? normalizedCheckpoint({
		version: storedRecord.version,
		sequence: storedRecord.sequence,
		event_hash: storedRecord.eventHash,
		previous_hash: storedRecord.previousHash,
		directory_hash: storedRecord.directoryHash,
	}) : null;
	if (!stored) {
		await writeRecord({ deviceUid: key, recordType: 'directory-checkpoint', accountUid: String(accountUid), ...current, observedAt: new Date().toISOString() });
		return { ok: true, firstObservation: true, checkpoint: current };
	}
	if (current.sequence < stored.sequence) return conflict('checkpoint_rollback', stored, current);
	if (current.sequence === stored.sequence) {
		if (current.eventHash !== stored.eventHash || current.directoryHash !== stored.directoryHash) return conflict('checkpoint_fork', stored, current);
		return { ok: true, firstObservation: false, checkpoint: current };
	}
	const continuity = await verifyForwardChain({ accountUid, stored, current });
	if (!continuity.ok) return continuity;
	await writeRecord({ deviceUid: key, recordType: 'directory-checkpoint', accountUid: String(accountUid), ...current, observedAt: new Date().toISOString() });
	return { ok: true, firstObservation: false, checkpoint: current };
};

export const assertDirectoryCheckpoint = async ({ accountUid, checkpoint, requireCheckpoint = true }) => {
	const result = await observeDirectoryCheckpoint({ accountUid, checkpoint, requireCheckpoint });
	if (result.ok) return result;
	const error = new Error('e2ee_directory_transparency_conflict');
	error.code = 'e2ee_directory_transparency_conflict';
	error.reason = result.reason;
	error.transparency = result;
	throw error;
};
