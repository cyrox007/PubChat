import assert from 'node:assert/strict';

globalThis.location = { origin: 'https://pubchat.ru' };

const { avatarFallbackDataUrl, publicAssetUrl } = await import('../src/utils/publicAssetUrl.js');

assert.equal(publicAssetUrl('/uploads/images/avatar.webp'), '/api/uploads/images/avatar.webp');
assert.equal(publicAssetUrl('uploads/images/avatar.webp'), '/api/uploads/images/avatar.webp');
assert.equal(publicAssetUrl('/static/default_male.webp'), '/api/static/default_male.webp');
assert.equal(publicAssetUrl('/api/uploads/images/avatar.webp'), '/api/uploads/images/avatar.webp');
assert.equal(
	publicAssetUrl('https://pubchat.ru/uploads/images/avatar.webp'),
	'/api/uploads/images/avatar.webp',
);
assert.equal(
	publicAssetUrl('https://pubchat.ru/static/default_male.webp?v=1#avatar'),
	'/api/static/default_male.webp?v=1#avatar',
);
assert.equal(
	publicAssetUrl('https://cdn.example.com/uploads/images/avatar.webp'),
	'https://cdn.example.com/uploads/images/avatar.webp',
);
assert.equal(publicAssetUrl('/images/frontend-logo.svg'), '/images/frontend-logo.svg');
assert.match(avatarFallbackDataUrl('A'), /^data:image\/svg\+xml/);

console.log('Public asset URL regression guard passed');
