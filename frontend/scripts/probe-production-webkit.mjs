import { webkit, devices } from '@playwright/test';
import { performance } from 'node:perf_hooks';

// Production transport probe in WebKit with an iPhone viewport / Safari UA.
// Unauthenticated only: no account, cookies, registration or push enrollment.
// WebKit on Linux is NOT a real iPhone networking stack or iCloud Private Relay.
const browser = await webkit.launch({ headless: true });
const context = await browser.newContext({
  ...devices['iPhone 13'],
  ignoreHTTPSErrors: false,
});
const page = await context.newPage();
const failed = [];
page.on('requestfailed', (req) => {
  // Do not log query parameters, response bodies, or cookies.
  try {
    const uri = new URL(req.url());
    failed.push({ path: uri.pathname, error: req.failure()?.errorText });
  } catch {}
});
try {
  const started = performance.now();
  const response = await page.goto('https://www.pubchat.ru/', {
    waitUntil: 'domcontentloaded', timeout: 20000,
  });
  console.log('WEBKIT iPhone-viewport root_status=' + response?.status()
    + ' domcontentloaded_ms=' + Math.round(performance.now() - started));
  const result = await page.evaluate(async () => {
    const origin = location.origin;
    const target = origin.replace(/^http/i, 'ws') + '/api/ws/v2/messenger';
    return await new Promise(resolve => {
      let finished = false;
      const ws = new WebSocket(target);
      const begun = performance.now();
      const done = (phase, code = null) => {
        if (finished) return;
        finished = true;
        clearTimeout(timer);
        resolve({ phase, closeCode: code, elapsedMs: Math.round(performance.now() - begun) });
      };
      const timer = setTimeout(() => {
        ws.close();
        done('handshake_timeout');
      }, 10000);
      ws.addEventListener('open', () => {
        // The unauthenticated connection should upgrade but will not become
        // ready: no ticket is issued to this session.
        ws.close(1000, 'Diagnostic handshake complete');
        done('open');
      });
      ws.addEventListener('error', () => done('error'));
      ws.addEventListener('close', event => done('closed', event.code));
    });
  });
  console.log('WEBKIT iPhone-viewport wss=' + JSON.stringify(result));
  console.log('WEBKIT iPhone-viewport request_failures=' + JSON.stringify(failed.slice(0, 12)));
} catch (error) {
  console.log('WEBKIT iPhone-viewport failure=' + error.name
    + ' detail=' + String(error.message).slice(0, 200));
} finally {
  await context.close();
  await browser.close();
}
