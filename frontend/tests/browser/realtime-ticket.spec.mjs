import { devices, expect, test } from '@playwright/test';

const WAIT_MS = 16000;

// Run against the CI same-origin backend, not production. The account is
// isolated to CI PostgreSQL. Mobile WebKit is Safari-like but not iOS hardware.
test('mobile WebKit: registration -> ticket -> WSS auth -> realtime_ready -> reload', async ({
  browser,
}, testInfo) => {
  test.skip(testInfo.project.name !== 'webkit', 'Safari-like realtime contract');

  const context = await browser.newContext({ ...devices['iPhone 13'] });
  const page = await context.newPage();
  const runtimeFailures = [];
  page.on('pageerror', (error) => runtimeFailures.push(String(error)));

  function nextMessengerReady() {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        page.off('websocket', seen);
        reject(new Error('Messenger WebSocket did not deliver realtime_ready within 16s'));
      }, WAIT_MS);
      const seen = (socket) => {
        if (!socket.url().includes('/api/ws/v2/messenger')) return;
        page.off('websocket', seen);
        let authed = false;
        socket.on('framesent', ({ payload }) => {
          // Inspect only the frame type, never the one-time ticket.
          try { if (JSON.parse(payload).type === 'auth') authed = true; } catch {}
        });
        socket.on('framereceived', ({ payload }) => {
          try {
            const frame = JSON.parse(payload);
            if (frame.type === 'realtime_ready') {
              clearTimeout(timer);
              resolve({ authed, protocol: frame.protocol, target: frame.target });
            }
          } catch {}
        });
        socket.on('close', () => {
          clearTimeout(timer);
          reject(new Error('Messenger WebSocket closed before realtime_ready'));
        });
      };
      page.on('websocket', seen);
    });
  }

  try {
    const handle = `pwrt${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
    await page.goto('/registration');
    await page.getByLabel('Как вас называть?').fill('Mobile WebKit realtime tester');
    await page.getByLabel('Уникальный адрес').fill(handle);
    await page.getByRole('button', { name: 'Продолжить' }).click();
    await page.getByLabel('Пароль', { exact: true }).fill('BrowserGate-2026!');
    await page.getByLabel('Повторите пароль').fill('BrowserGate-2026!');

    const firstReady = nextMessengerReady();
    const firstTicket = page.waitForResponse((response) => (
      response.url().includes('/api/realtime/v2/tickets')
      && response.request().method() === 'POST'
    ));
    await page.getByRole('button', { name: 'Войти в PubChat' }).click();
    const issued = await firstTicket;
    expect(issued.status(), 'Realtime ticket must be issued by backend').toBe(201);
    expect(await firstReady).toMatchObject({
      authed: true,
      protocol: 2,
      target: 'messenger',
    });

    // Safari reload destroys in-memory access token but preserves a same-origin
    // HttpOnly cookie. The client must refresh then issue a NEW one-time ticket.
    const reloadReady = nextMessengerReady();
    const refreshed = page.waitForResponse((response) => (
      response.url().includes('/api/identity/v2/refresh')
      && response.request().method() === 'POST'
    ));
    await page.reload();
    expect((await refreshed).status()).toBe(200);
    expect(await reloadReady).toMatchObject({
      authed: true,
      protocol: 2,
      target: 'messenger',
    });
    expect(runtimeFailures).toEqual([]);
  } finally {
    await context.close();
  }
});
