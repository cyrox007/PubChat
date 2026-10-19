import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';

// The actual CSS layer loaded last in main.js. The component's scoped CSS is
// extracted to exercise competing production defaults, not a mock layout.
const roomCSS = readFileSync(new URL('../../src/assets/mobile-room-v2.css', import.meta.url), 'utf8');
const densityCSS = readFileSync(new URL('../../src/assets/message-density-depth-v3.css', import.meta.url), 'utf8');
const chatComponent = readFileSync(new URL('../../src/components/Message/ChatMessage.vue', import.meta.url), 'utf8');
const chatCSS = chatComponent.match(/<style scoped>([\s\S]*?)<\/style>/)?.[1] ?? '';
const dmComponent = readFileSync(new URL('../../src/components/Message/PrivateMessage.vue', import.meta.url), 'utf8');
const dmCSS = dmComponent.match(/<style scoped>([\s\S]*?)<\/style>/)?.[1] ?? '';

test('Space message text stays content-sized while reply controls retain 44px targets', async ({ page }) => {
  for (const width of [320, 390, 1440]) {
    await page.setViewportSize({ width, height: 760 });
    await page.setContent(`
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <style>
        * { box-sizing: border-box }
        html, body { margin: 0 }
        .app-shell, .message-stream { width: 100%; }
        .message-stream { display: flex; flex-direction: column; padding: 10px; }
      </style>
      <main class="app-shell">
        <div class="message-stream">
          <article class="message other-user">
            <header class="message-header"><span class="avatar"></span>
              <span class="user-info"><strong>Аня</strong><time class="timestamp">18:30</time></span>
            </header>
            <div class="message-body"><p class="message-text">Ок</p></div>
            <footer class="message-footer">
              <div class="message-actions"><button class="message-actions__toggle">...</button></div>
              <button class="reply-button" aria-label="Ответить">↩</button>
            </footer>
          </article>
          <article class="message sender">
            <header class="message-header"><span class="avatar"></span>
              <span class="user-info"><strong>Вы</strong><time class="timestamp">18:32</time></span>
            </header>
            <div class="message-body"><p class="message-text">Да</p></div>
            <footer class="message-footer">
              <div class="message-actions"><button class="message-actions__toggle">...</button></div>
              <button class="reply-button" aria-label="Ответить">↩</button>
              <span class="message-status">✓</span>
            </footer>
          </article>
        </div>
      </main>
    `);
    await page.addStyleTag({ content: chatCSS + '\n' + roomCSS + '\n' + densityCSS });
    for (const bubble of await page.locator('.message-stream > .message').all()) {
      const box = await bubble.boundingBox();
      expect(box.height, 'short text should not expand for reply buttons').toBeLessThan(96);
      expect(box.width, 'short text should wrap to content').toBeLessThan(200);
      const action = await bubble.getByRole('button', { name: 'Ответить' }).boundingBox();
      expect(action.width).toBeCloseTo(44, 2);
      expect(action.height).toBeCloseTo(44, 2);
      expect(action.x).toBeGreaterThanOrEqual(0);
      expect(action.x + action.width).toBeLessThanOrEqual(width + 1);
    }
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - innerWidth);
    expect(overflow, `horizontal overflow at ${width}px`).toBeLessThanOrEqual(1);
  }
});

test('Messenger bubble remains compact with actions outside its body', async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 760 });
  await page.setContent(`
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>*{box-sizing:border-box}html,body{margin:0}.app-shell{width:100%}.dm-stream{width:100%;padding:10px}</style>
    <main class="app-shell">
      <div class="dm-stream"><article class="message sent">
        <div class="message-body"><p class="message-text">Привет</p></div>
        <div class="message-actions"><button class="message-actions__toggle">...</button></div>
        <footer class="message-meta"><time class="message-time">18:32</time></footer>
      </article></div>
    </main>
  `);
  await page.addStyleTag({ content: dmCSS + '\n' + densityCSS });
  const bubble = await page.locator('.dm-stream .message-body').boundingBox();
  const action = await page.locator('.dm-stream .message-actions__toggle').boundingBox();
  expect(bubble.width).toBeLessThan(170);
  expect(bubble.height).toBeLessThan(70);
  expect(action.height).toBeCloseTo(44, 2);
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
});
