import { onMounted, onUnmounted } from 'vue';

import SpacesService from '@/API/SpacesService';

export const DISCOVERY_LIVE_REFRESH_MS = 20_000;
const LIVE_REASON_CODES = new Set(['live_presence', 'live_conversation']);

const liveReasons = (live) => {
	const reasons = [];
	if (live?.conversation?.active) {
		reasons.push({ code: 'live_conversation', label: 'Разговор идёт сейчас' });
	}
	if (Number.isInteger(live?.present_count) && live.present_count > 0) {
		reasons.push({ code: 'live_presence', label: `${live.present_count} сейчас здесь` });
	}
	return reasons;
};

export const mergeDiscoveryLiveState = (spaces, liveItems) => {
	const liveByUid = new Map((liveItems || []).map((item) => [String(item.space_uid), item]));

	return spaces.map((space) => {
		const live = liveByUid.get(String(space.uid)) || null;
		const discovery = space.discovery || {};
		const stableReasons = (discovery.reasons || []).filter((reason) => !LIVE_REASON_CODES.has(reason?.code));
		return {
			...space,
			discovery: {
				...discovery,
				live,
				reasons: [...liveReasons(live), ...stableReasons],
			},
		};
	});
};

export const useSpaceDiscoveryLivePolling = (spaces) => {
	let timerId = null;
	let requestInFlight = false;
	let stopped = false;

	const refresh = async () => {
		if (stopped || requestInFlight || document.hidden || !spaces.value.length) return;
		requestInFlight = true;
		try {
			const requestedUids = spaces.value.map((space) => space.uid).filter(Boolean).slice(0, 50);
			if (!requestedUids.length) return;

			const response = await SpacesService.liveState(requestedUids);
			if (stopped) return;
			spaces.value = mergeDiscoveryLiveState(spaces.value, response.data.spaces || []);
		} catch (error) {
			// Live context is progressive enhancement: keep the last known card state
			// and do not turn a transient realtime failure into a Discovery error.
			console.warn('Не удалось обновить live-состояние пространств:', error);
		} finally {
			requestInFlight = false;
		}
	};

	const schedule = () => {
		if (timerId !== null || stopped) return;
		timerId = window.setInterval(refresh, DISCOVERY_LIVE_REFRESH_MS);
	};

	const unschedule = () => {
		if (timerId === null) return;
		window.clearInterval(timerId);
		timerId = null;
	};

	const handleVisibilityChange = () => {
		if (document.hidden) {
			unschedule();
			return;
		}
		void refresh();
		schedule();
	};

	onMounted(() => {
		stopped = false;
		document.addEventListener('visibilitychange', handleVisibilityChange);
		schedule();
	});

	onUnmounted(() => {
		stopped = true;
		unschedule();
		document.removeEventListener('visibilitychange', handleVisibilityChange);
	});

	return { refresh };
};
