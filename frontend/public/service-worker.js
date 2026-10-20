const SHELL_CACHE = 'pubchat-shell-v1';
const RUNTIME_CACHE = 'pubchat-runtime-v1';

const SHELL_URLS = [
  '/',
  '/index.html',
  '/favicons/site.webmanifest',
  '/favicons/favicon-32x32.png',
  '/favicons/android-chrome-192x192.png',
  '/favicons/android-chrome-512x512.png',
];

const STATIC_DESTINATIONS = new Set(['script', 'style', 'font', 'image']);

const isStaticAsset = (request, url) => {
  if (!STATIC_DESTINATIONS.has(request.destination)) return false;
  return url.pathname.startsWith('/assets/')
    || url.pathname.startsWith('/favicons/')
    || url.pathname === '/favicon.ico';
};

const safePushUrl = (value) => {
  if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//')) return '/messenger';
  return value;
};

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE)
      .then((cache) => cache.addAll(SHELL_URLS))
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys
          .filter((key) => key.startsWith('pubchat-') && ![SHELL_CACHE, RUNTIME_CACHE].includes(key))
          .map((key) => caches.delete(key)),
      ))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // Navigation gets network-first semantics. The cached index is only an offline
  // application shell; auth/API state is never persisted by this worker.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response.ok && response.headers.get('content-type')?.includes('text/html')) {
            const clone = response.clone();
            caches.open(SHELL_CACHE).then((cache) => cache.put('/index.html', clone));
          }
          return response;
        })
        .catch(async () => (
          (await caches.match('/index.html'))
          || (await caches.match('/'))
          || Response.error()
        )),
    );
    return;
  }

  // Only static browser resources are cached. fetch/XHR/API requests have an
  // empty destination and intentionally bypass the service worker cache.
  if (!isStaticAsset(request, url)) return;

  event.respondWith(
    caches.match(request).then((cached) => {
      const network = fetch(request).then((response) => {
        if (response.ok) {
          const clone = response.clone();
          caches.open(RUNTIME_CACHE).then((cache) => cache.put(request, clone));
        }
        return response;
      });
      return cached || network;
    }),
  );
});

self.addEventListener('push', (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch {
    payload = {};
  }

  const title = typeof payload.title === 'string' && payload.title.trim()
    ? payload.title.trim().slice(0, 120)
    : 'PubChat';
  const body = typeof payload.body === 'string' && payload.body.trim()
    ? payload.body.trim().slice(0, 220)
    : 'У вас есть новое уведомление.';
  const tag = typeof payload.tag === 'string' && payload.tag.trim()
    ? payload.tag.trim().slice(0, 120)
    : 'pubchat-notification';

  event.waitUntil((async () => {
    // A websocket can stay connected in a minimized tab. Show OS alerts when
    // backgrounded, but avoid duplicating the in-app sound while focused.
    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    const viewingApp = windows.some((client) => (
      new URL(client.url).origin === self.location.origin
      && client.focused === true
      && client.visibilityState === 'visible'
    ));
    if (viewingApp) return;
    await self.registration.showNotification(title, {
      body,
      tag,
      renotify: false,
      icon: '/favicons/android-chrome-192x192.png',
      badge: '/favicons/favicon-32x32.png',
      data: { url: safePushUrl(payload.url) },
    });
  })());
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const path = safePushUrl(event.notification?.data?.url);
  const targetUrl = new URL(path, self.location.origin).href;

  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    const existing = windows.find((client) => new URL(client.url).origin === self.location.origin);
    if (existing) {
      await existing.focus();
      if ('navigate' in existing) await existing.navigate(targetUrl);
      return;
    }
    if (self.clients.openWindow) await self.clients.openWindow(targetUrl);
  })());
});
