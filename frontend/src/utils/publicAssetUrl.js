const apiBaseUrl = String(import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/+$/, '');
const backendPublicPath = /^\/(?:uploads|static)\//i;
const legacyApiPublicPath = /^\/api\/(?:uploads|static)\//i;

export function publicAssetUrl(value) {
	if (!value) return '';
	const raw = String(value).trim();
	if (!raw) return '';
	if (/^(https?:|blob:|data:)/i.test(raw)) return raw;

	const path = `/${raw.replace(/^\/+/, '')}`;

	// Public backend media is served through the API reverse-proxy prefix in
	// production. Keep already-prefixed historical values valid without ever
	// producing /api/api/... and support custom absolute API bases as well.
	if (legacyApiPublicPath.test(path)) {
		return apiBaseUrl === '/api' ? path : `${apiBaseUrl}${path.slice('/api'.length)}`;
	}
	if (backendPublicPath.test(path)) return `${apiBaseUrl}${path}`;

	// Frontend-owned assets (for example /images/...) stay on the SPA origin.
	return path;
}

export function avatarFallbackDataUrl(label = '?') {
	const initial = String(label || '?').trim().slice(0, 1).toUpperCase() || '?';
	const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="32" fill="#f3e7ef"/><text x="32" y="38" text-anchor="middle" font-family="system-ui,sans-serif" font-size="28" font-weight="700" fill="#9b2768">${initial.replace(/[&<>"']/g, '')}</text></svg>`;
	return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
}

export function handleAvatarImageError(event, label = '?') {
	const image = event?.currentTarget;
	if (!image || image.dataset.avatarFallbackApplied === '1') return;
	image.dataset.avatarFallbackApplied = '1';
	image.src = avatarFallbackDataUrl(label);
}
