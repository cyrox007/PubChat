import CryptoService from '@/API/CryptoService';
import { sendEncryptedPayload } from '@/crypto/messengerE2EE';

const VERSION = 'pubchat-e2ee-attachment-v1';
const encoder = new TextEncoder();
const objectUrlCache = new Map();

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

const bytesFromDataUrl = (value) => {
	const match = /^data:([^;,]*)(;base64)?,(.*)$/s.exec(String(value || ''));
	if (!match) throw new Error('e2ee_attachment_source_invalid');
	const mime = match[1] || 'application/octet-stream';
	if (match[2]) {
		const binary = atob(match[3]);
		return { mime, bytes: Uint8Array.from(binary, (char) => char.charCodeAt(0)) };
	}
	return { mime, bytes: encoder.encode(decodeURIComponent(match[3])) };
};

const attachmentAad = (uid) => encoder.encode(JSON.stringify({ v: VERSION, uid }));

const sha256Hex = async (bytes) => {
	const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', bytes));
	return [...digest].map((value) => value.toString(16).padStart(2, '0')).join('');
};

export const sendEncryptedAttachment = async ({
	receiverUid,
	file,
	kind,
	caption = '',
	frontId,
	deviceLabel = null,
}) => {
	if (!file?.url) throw new Error('e2ee_attachment_source_missing');
	const attachmentUid = crypto.randomUUID();
	const source = bytesFromDataUrl(file.url);
	const rawKey = crypto.getRandomValues(new Uint8Array(32));
	const nonce = crypto.getRandomValues(new Uint8Array(12));
	let uploaded = false;
	try {
		const key = await crypto.subtle.importKey('raw', rawKey, { name: 'AES-GCM' }, false, ['encrypt']);
		const ciphertext = new Uint8Array(await crypto.subtle.encrypt(
			{ name: 'AES-GCM', iv: nonce, additionalData: attachmentAad(attachmentUid), tagLength: 128 },
			key,
			source.bytes,
		));
		const ciphertextSha256 = await sha256Hex(ciphertext);
		const upload = await CryptoService.uploadEncryptedAttachment(attachmentUid, ciphertext);
		uploaded = true;
		if (upload.data?.ciphertext_sha256 !== ciphertextSha256 || Number(upload.data?.ciphertext_size) !== ciphertext.byteLength) {
			throw new Error('e2ee_attachment_upload_integrity_failed');
		}
		const attachment = {
			uid: attachmentUid,
			version: VERSION,
			key: b64(rawKey),
			nonce: b64(nonce),
			ciphertext_sha256: ciphertextSha256,
			kind: ['image', 'video', 'audio', 'voice', 'file'].includes(kind) ? kind : 'file',
			name: String(file.name || 'Файл').slice(0, 255),
			mime_type: String(file.type || source.mime || 'application/octet-stream').slice(0, 160),
			size: source.bytes.byteLength,
			duration: Number(file.duration) || 0,
			waveform: Array.isArray(file.waveform) ? file.waveform.slice(0, 128) : [],
		};
		const result = await sendEncryptedPayload({
			receiverUid,
			frontId,
			attachmentUid,
			deviceLabel,
			payload: { type: 'attachment', attachment, caption: String(caption || '') },
		});
		if (!result.encrypted) throw new Error(result.reason || 'e2ee_attachment_send_failed');
		return result;
	} catch (error) {
		if (uploaded) {
			try { await CryptoService.deleteEncryptedAttachment(attachmentUid); } catch { /* already attached or cleanup best-effort */ }
		}
		throw error;
	} finally {
		rawKey.fill(0);
		nonce.fill(0);
		source.bytes.fill(0);
	}
};

export const resolveEncryptedAttachmentUrl = async (attachment) => {
	const uid = attachment?.uid;
	if (!uid || !attachment?.key || !attachment?.nonce) throw new Error('e2ee_attachment_descriptor_invalid');
	if (objectUrlCache.has(uid)) return objectUrlCache.get(uid);

	const pending = (async () => {
		const response = await CryptoService.encryptedAttachment(uid);
		const ciphertext = new Uint8Array(response.data);
		const hash = await sha256Hex(ciphertext);
		if (hash !== attachment.ciphertext_sha256) throw new Error('e2ee_attachment_ciphertext_integrity_failed');
		const rawKey = unb64(attachment.key);
		try {
			if (rawKey.byteLength !== 32) throw new Error('e2ee_attachment_key_invalid');
			const key = await crypto.subtle.importKey('raw', rawKey, { name: 'AES-GCM' }, false, ['decrypt']);
			const plaintext = await crypto.subtle.decrypt(
				{
					name: 'AES-GCM',
					iv: unb64(attachment.nonce),
					additionalData: attachmentAad(uid),
					tagLength: 128,
				},
				key,
				ciphertext,
			);
			if (attachment.size && plaintext.byteLength !== Number(attachment.size)) {
				throw new Error('e2ee_attachment_plaintext_size_mismatch');
			}
			return URL.createObjectURL(new Blob([plaintext], { type: attachment.mime_type || 'application/octet-stream' }));
		} finally {
			rawKey.fill(0);
			ciphertext.fill(0);
		}
	})();
	objectUrlCache.set(uid, pending);
	try {
		return await pending;
	} catch (error) {
		objectUrlCache.delete(uid);
		throw error;
	}
};
