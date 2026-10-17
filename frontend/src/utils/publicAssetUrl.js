const viteEnv = import.meta.env || {};
const apiBaseUrl = String(viteEnv.VITE_API_BASE_URL || '/api').replace(/\/+$/, '');
const backendPublicPath = /^\/(?:uploads|static)\//i;
const legacyApiPublicPath = /^\/api\/(?:uploads|static)\//i;

function normalizeBackendPath(pathname) {
	const path = `/${String(pathname || '').replace(/^\/+/, '')}`;
	if (legacyApiPublicPath.test(path)) {
		return apiBaseUrl === '/api' ? path : `${apiBaseUrl}${path.slice('/api'.length)}`;
	}
	if (backendPublicPath.test(path)) return `${apiBaseUrl}${path}`;
	return path;
}

export function publicAssetUrl(value) {
	if (!value) return '';
	const raw = String(value).trim();
	if (!raw) return '';
	if (/^(?:blob:|data:)/i.test(raw)) return raw;

	if (/^https?:\/\//i.test(raw)) {
		try {
			const parsed = new URL(raw);
			const currentOrigin = globalThis.location?.origin || '';
			if (currentOrigin && parsed.origin === currentOrigin && (backendPublicPath.test(parsed.pathname) || legacyApiPublicPath.test(parsed.pathname))) {
				return `${normalizeBackendPath(parsed.pathname)}${parsed.search}${parsed.hash}`;
			}
		} catch (_) {
			// Keep malformed historical values unchanged so the image error fallback can take over.
		}
		return raw;
	}

	return normalizeBackendPath(raw);
}

export function avatarFallbackDataUrl(label = '?') {
	const initial = String(label || '?').trim().slice(0, 1).toUpperCase() || '?';
	const safeInitial = initial.replace(/[&<>"']/g, '');
	const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="32" fill="#f3e7ef"/><text x="32" y="38" text-anchor="middle" font-family="system-ui,sans-serif" font-size="28" font-weight="700" fill="#9b2768">${safeInitial}</text></svg>`;
	return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
}

export function handleAvatarImageError(event, label = '?') {
	const image = event?.currentTarget;
	if (!image || image.dataset.avatarFallbackApplied === '1') return;
	image.dataset.avatarFallbackApplied = '1';
	image.src = avatarFallbackDataUrl(label);
}
