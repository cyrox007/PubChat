import { computed, reactive } from 'vue';
import { v4 as uuidv4 } from 'uuid';

import CallService from '@/API/CallService';
import CryptoService from '@/API/CryptoService';
import RealtimeService from '@/API/RealtimeService';

const state = reactive({
	cameraEnabled: true,
	callUid: null,
	connectionState: 'idle',
	deviceIdentityBound: false,
	error: null,
	iceTransportPolicy: null,
	incomingSdp: null,
	localStream: null,
	mediaSecurity: null,
	mode: 'audio',
	muted: false,
	peer: null,
	peerDirectoryContinuity: 'not_checked',
	peerUid: null,
	phase: 'idle',
	remoteStream: null,
	securityClaim: null,
	signalingE2ee: false,
	socket: null,
	verifiedApplicationE2ee: false,
});

let peerConnection = null;
let heartbeatTimer = null;
let pendingCandidates = [];
let reconnectTimer = null;
let manualDisconnect = false;
let connectPromise = null;

const emitState = () => window.dispatchEvent(new CustomEvent('pubchat:call-state', { detail: { ...state } }));
const setPhase = (phase, error = null) => { state.phase = phase; state.error = error; emitState(); };
const stopHeartbeat = () => { if (heartbeatTimer) clearInterval(heartbeatTimer); heartbeatTimer = null; };

const sendSignal = (signalType, payload = {}) => {
	if (state.connectionState !== 'connected' || state.socket?.readyState !== WebSocket.OPEN || !state.peerUid || !state.callUid) {
		throw new Error('Call signaling is unavailable');
	}
	state.socket.send(JSON.stringify({ action: signalType, target_uid: state.peerUid, call_uid: state.callUid, ...payload }));
};

const loadIceConfig = async () => {
	const response = await CallService.iceConfig();
	const iceServers = Array.isArray(response.data?.ice_servers) ? response.data.ice_servers : [];
	const iceTransportPolicy = response.data?.ice_transport_policy === 'relay' ? 'relay' : 'all';
	const security = response.data?.security || {};
	state.iceTransportPolicy = iceTransportPolicy;
	state.mediaSecurity = security.media_transport || response.data?.media_security || 'webrtc-dtls-srtp';
	state.signalingE2ee = security.signaling_e2ee === true || response.data?.signaling_e2ee === true;
	state.deviceIdentityBound = security.device_identity_bound === true;
	state.verifiedApplicationE2ee = security.verified_application_e2ee === true;
	state.securityClaim = security.claim || 'transport-encrypted-unverified';
	return { iceServers, iceTransportPolicy };
};

const checkPeerDirectoryContinuity = async () => {
	if (!state.peerUid) throw new Error('call_peer_missing');
	state.peerDirectoryContinuity = 'checking';
	try {
		const response = await CryptoService.accountDevices(state.peerUid);
		const policy = response.data?.encryption || null;
		const devices = response.data?.devices || [];
		if (policy?.effective_mode === 'plaintext') {
			state.peerDirectoryContinuity = 'plaintext';
			return;
		}
		state.peerDirectoryContinuity = devices.length && response.data?.directory_checkpoint ? 'checked' : 'not_available';
	} catch (error) {
		state.peerDirectoryContinuity = 'conflict';
		throw error;
	}
};

const cleanupPeer = () => {
	pendingCandidates = [];
	if (peerConnection) {
		try {
			peerConnection.ontrack = null;
			peerConnection.onicecandidate = null;
			peerConnection.onconnectionstatechange = null;
			peerConnection.close();
		} catch (_) {}
	}
	peerConnection = null;
	state.localStream?.getTracks?.().forEach((track) => track.stop());
	state.remoteStream?.getTracks?.().forEach((track) => track.stop());
	state.localStream = null;
	state.remoteStream = null;
	state.muted = false;
	state.cameraEnabled = true;
	state.incomingSdp = null;
};

const resetCall = () => {
	cleanupPeer();
	state.callUid = null;
	state.peerUid = null;
	state.peer = null;
	state.mode = 'audio';
	state.iceTransportPolicy = null;
	state.mediaSecurity = null;
	state.signalingE2ee = false;
	state.deviceIdentityBound = false;
	state.verifiedApplicationE2ee = false;
	state.securityClaim = null;
	state.peerDirectoryContinuity = 'not_checked';
	setPhase('idle');
};

const acquireMedia = async (mode) => {
	if (!window.isSecureContext && !['localhost', '127.0.0.1'].includes(window.location.hostname)) throw new Error('secure_context_required');
	if (!navigator.mediaDevices?.getUserMedia) throw new Error('media_unsupported');
	const stream = await navigator.mediaDevices.getUserMedia(
		mode === 'video'
			? { audio: true, video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 } } }
			: { audio: true, video: false },
	);
	state.localStream = stream;
	return stream;
};

const createPeerConnection = (configuration) => {
	if (peerConnection) return peerConnection;
	const pc = new RTCPeerConnection(configuration);
	peerConnection = pc;
	state.remoteStream = new MediaStream();
	pc.ontrack = (event) => {
		event.streams?.[0]?.getTracks()?.forEach((track) => {
			if (!state.remoteStream.getTracks().some((item) => item.id === track.id)) state.remoteStream.addTrack(track);
		});
		emitState();
	};
	pc.onicecandidate = (event) => {
		if (event.candidate) {
			try { sendSignal('call_ice', { candidate: event.candidate.toJSON ? event.candidate.toJSON() : event.candidate }); } catch (_) {}
		}
	};
	pc.onconnectionstatechange = () => {
		if (pc.connectionState === 'connected') setPhase('active');
		else if (['failed', 'disconnected'].includes(pc.connectionState) && ['active', 'connecting'].includes(state.phase)) {
			setPhase('error', 'Связь прервана');
		}
	};
	return pc;
};

const attachLocalTracks = (pc, stream) => stream.getTracks().forEach((track) => pc.addTrack(track, stream));
const flushCandidates = async () => {
	if (!peerConnection?.remoteDescription) return;
	const queue = pendingCandidates;
	pendingCandidates = [];
	for (const candidate of queue) {
		try { await peerConnection.addIceCandidate(candidate); } catch (_) {}
	}
};

const handleSignal = async (data) => {
	if (data.type !== 'call_signal') return;
	const fromUid = data.from_uid;
	if (data.signal_type === 'call_offer') {
		if (data.ice_restart === true && state.callUid === data.call_uid && state.peerUid === fromUid && peerConnection) {
			try {
				if (peerConnection.signalingState !== 'stable') return;
				await peerConnection.setRemoteDescription(new RTCSessionDescription(data.sdp));
				const answer = await peerConnection.createAnswer();
				await peerConnection.setLocalDescription(answer);
				sendSignal('call_answer', { sdp: peerConnection.localDescription.toJSON() });
				await flushCandidates();
				setPhase('connecting');
			} catch (_) { setPhase('error', 'Не удалось восстановить соединение'); }
			return;
		}
		if (state.phase !== 'idle') {
			const oldPeer = state.peerUid;
			const oldCall = state.callUid;
			state.peerUid = fromUid;
			state.callUid = data.call_uid;
			try { sendSignal('call_decline', { reason: 'busy' }); } catch (_) {}
			state.peerUid = oldPeer;
			state.callUid = oldCall;
			return;
		}
		state.callUid = data.call_uid;
		state.peerUid = fromUid;
		state.peer = { uid: fromUid };
		state.mode = data.mode === 'video' ? 'video' : 'audio';
		state.incomingSdp = data.sdp;
		state.peerDirectoryContinuity = 'pending';
		try { sendSignal('call_ringing'); } catch (_) {}
		setPhase('incoming');
		return;
	}
	if (!state.callUid || data.call_uid !== state.callUid || fromUid !== state.peerUid) return;
	if (data.signal_type === 'call_answer') {
		if (!peerConnection) return;
		await peerConnection.setRemoteDescription(new RTCSessionDescription(data.sdp));
		await flushCandidates();
		setPhase('connecting');
		return;
	}
	if (data.signal_type === 'call_ice') {
		if (!peerConnection?.remoteDescription) pendingCandidates.push(data.candidate);
		else try { await peerConnection.addIceCandidate(data.candidate); } catch (_) {}
		return;
	}
	if (data.signal_type === 'call_decline') {
		cleanupPeer();
		const reason = data.reason === 'busy'
			? 'Пользователь занят'
			: data.reason === 'security_unavailable'
				? 'Звонок отклонён: не удалось подтвердить состояние E2EE-устройств'
				: 'Звонок отклонён';
		setPhase('ended', reason);
		return;
	}
	if (data.signal_type === 'call_end') {
		cleanupPeer();
		setPhase('ended', data.reason || null);
		return;
	}
};

const connect = async () => {
	if (state.connectionState === 'connected' && state.socket?.readyState === WebSocket.OPEN) return;
	if (connectPromise) return connectPromise;
	manualDisconnect = false;
	state.connectionState = 'connecting';
	connectPromise = new Promise(async (resolve, reject) => {
		try {
			const ticketResponse = await RealtimeService.createTicket('messenger');
			const socket = RealtimeService.openSocket('/ws/v2/calls');
			state.socket = socket;
			const fail = (error) => {
				if (connectPromise) {
					state.connectionState = 'error';
					connectPromise = null;
					reject(error instanceof Error ? error : new Error('call_signaling_failed'));
				}
			};
			socket.onopen = () => socket.send(JSON.stringify({ type: 'auth', ticket: ticketResponse.data.ticket }));
			socket.onmessage = async (event) => {
				let data;
				try { data = JSON.parse(event.data); } catch (_) { return; }
				if (data.type === 'realtime_ready') {
					state.connectionState = 'connected';
					stopHeartbeat();
					heartbeatTimer = setInterval(() => {
						if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ type: 'heartbeat', action: 'heartbeat' }));
					}, Math.max(10, data.heartbeat_seconds || 25) * 1000);
					connectPromise = null;
					resolve();
					return;
				}
				if (data.type === 'ping') { socket.send(JSON.stringify({ type: 'pong' })); return; }
				if (data.type === 'call_error' && data.error_type === 'call_rate_limited') {
					setPhase('error', 'Слишком много действий со звонком. Попробуйте чуть позже.');
					return;
				}
				await handleSignal(data);
			};
			socket.onerror = () => { if (state.connectionState !== 'connected') fail(new Error('call_signaling_socket_error')); };
			socket.onclose = () => {
				stopHeartbeat();
				state.socket = null;
				const wasConnecting = state.connectionState === 'connecting';
				state.connectionState = 'idle';
				if (wasConnecting && connectPromise) fail(new Error('call_signaling_closed'));
				if (!manualDisconnect) {
					clearTimeout(reconnectTimer);
					reconnectTimer = setTimeout(() => connect().catch(() => {}), 2000);
				}
			};
		} catch (error) {
			state.connectionState = 'error';
			connectPromise = null;
			reject(error);
		}
	});
	return connectPromise;
};

const disconnect = () => {
	manualDisconnect = true;
	clearTimeout(reconnectTimer);
	stopHeartbeat();
	connectPromise = null;
	if (state.socket) try { state.socket.close(1000, 'Client disconnect'); } catch (_) {}
	state.socket = null;
	state.connectionState = 'idle';
	if (state.phase !== 'idle') resetCall();
};

const securityErrorMessage = (error) => {
	if (error?.code === 'e2ee_directory_transparency_conflict') return 'Проверка истории E2EE-устройств выявила конфликт. Звонок не начат.';
	if (error?.code === 'e2ee_devices_not_ready') return 'E2EE выбран, но криптографические устройства собеседника не готовы.';
	return null;
};

const start = async (peer, mode = 'audio') => {
	if (state.phase !== 'idle' && state.phase !== 'ended') throw new Error('Call already active');
	if (state.phase === 'ended') resetCall();
	await connect();
	state.callUid = uuidv4();
	state.peerUid = typeof peer === 'string' ? peer : peer?.uid;
	state.peer = typeof peer === 'string' ? { uid: peer } : peer;
	state.mode = mode === 'video' ? 'video' : 'audio';
	try {
		const configuration = await loadIceConfig();
		await checkPeerDirectoryContinuity();
		const stream = await acquireMedia(state.mode);
		const pc = createPeerConnection(configuration);
		attachLocalTracks(pc, stream);
		const offer = await pc.createOffer();
		await pc.setLocalDescription(offer);
		sendSignal('call_offer', { mode: state.mode, sdp: pc.localDescription.toJSON ? pc.localDescription.toJSON() : pc.localDescription });
		setPhase('outgoing');
	} catch (error) {
		cleanupPeer();
		setPhase('error', securityErrorMessage(error) || (error?.response?.data?.detail?.error_type === 'call_ice_unavailable'
			? 'Безопасная конфигурация звонка сейчас недоступна'
			: 'Не удалось начать звонок'));
		throw error;
	}
};

const accept = async () => {
	if (state.phase !== 'incoming' || !state.incomingSdp) return;
	try {
		const configuration = await loadIceConfig();
		await checkPeerDirectoryContinuity();
		const stream = await acquireMedia(state.mode);
		const pc = createPeerConnection(configuration);
		attachLocalTracks(pc, stream);
		await pc.setRemoteDescription(new RTCSessionDescription(state.incomingSdp));
		await flushCandidates();
		const answer = await pc.createAnswer();
		await pc.setLocalDescription(answer);
		sendSignal('call_answer', { sdp: pc.localDescription.toJSON ? pc.localDescription.toJSON() : pc.localDescription });
		state.incomingSdp = null;
		setPhase('connecting');
	} catch (error) {
		const securityMessage = securityErrorMessage(error);
		try { sendSignal('call_decline', { reason: securityMessage ? 'security_unavailable' : 'media_unavailable' }); } catch (_) {}
		cleanupPeer();
		setPhase('error', securityMessage || 'Не удалось подготовить защищённое соединение или получить доступ к камере/микрофону');
	}
};

const decline = (reason = 'declined') => { try { sendSignal('call_decline', { reason }); } catch (_) {} cleanupPeer(); setPhase('ended'); };
const end = (reason = 'ended') => { try { sendSignal('call_end', { reason }); } catch (_) {} cleanupPeer(); setPhase('ended'); };
const dismiss = () => resetCall();
const toggleMute = () => { state.muted = !state.muted; state.localStream?.getAudioTracks()?.forEach((track) => { track.enabled = !state.muted; }); };
const toggleCamera = () => { state.cameraEnabled = !state.cameraEnabled; state.localStream?.getVideoTracks()?.forEach((track) => { track.enabled = state.cameraEnabled; }); };
const switchCamera = async () => {
	if (state.mode !== 'video' || !state.localStream) return;
	const current = state.localStream.getVideoTracks()[0];
	const facing = current?.getSettings?.().facingMode === 'environment' ? 'user' : 'environment';
	try {
		const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: facing }, audio: false });
		const replacement = stream.getVideoTracks()[0];
		const sender = peerConnection?.getSenders?.().find((item) => item.track?.kind === 'video');
		if (sender) await sender.replaceTrack(replacement);
		if (current) { state.localStream.removeTrack(current); current.stop(); }
		state.localStream.addTrack(replacement);
		emitState();
	} catch (_) {}
};

export function useWebRtcCall() {
	return {
		state,
		isBusy: computed(() => state.phase !== 'idle' && state.phase !== 'ended'),
		connect,
		disconnect,
		start,
		accept,
		decline,
		end,
		dismiss,
		toggleMute,
		toggleCamera,
		switchCamera,
	};
}