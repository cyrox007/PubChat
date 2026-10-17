export function publicAssetUrl(value) {
	if (!value) return '';
	const raw = String(value).trim();
	if (!raw) return '';
	if (/^(https?:|blob:|data:)/i.test(raw)) return raw;
	if (raw.startsWith('/')) return raw;
	return `/${raw.replace(/^\/+/, '')}`;
}
