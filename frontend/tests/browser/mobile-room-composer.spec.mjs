import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';

// Render the actual production CSS without requiring a seeded Space/chat account.
// The regression was a 9rem second column stealing room from the text input.
const composerCSS = readFileSync(new URL('../../src/assets/composer-single-line.css', import.meta.url), 'utf8');
const roomCSS = readFileSync(new URL('../../src/assets/mobile-room-v2.css', import.meta.url), 'utf8');

test('mobile Space composer gets full width, 44px controls and independent presence row', async ({ page }) => {
  for (const width of [320, 344, 390]) {
    await page.setViewportSize({ width, height: 760 });
    await page.setContent(`
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <style>* { box-sizing: border-box } html, body { margin: 0 } .app-shell { width: 100%; }</style>
      <div class="app-shell">
        <div class="conversation-area" style="width:100%;height:600px">
          <section class="message-stream">Разговор</section>
          <section class="live-presence">
            <span class="live-presence__copy">
              <span class="live-presence__status"><span class="live-presence__label">
                <span class="live-presence__place">Root</span></span>Вы здесь</span>
            </span>
          </section>
          <section class="composer">
            <div class="composer__bar">
              <button class="icon-btn" aria-label="Эмодзи">☺</button>
              <input aria-label="Сообщение" placeholder="Сообщение" />
              <button class="icon-btn" aria-label="Прикрепить">+</button>
              <button class="icon-btn" aria-label="Голосовое">🎤</button>
              <button class="icon-btn" aria-label="Видео">▣</button>
            </div>
          </section>
        </div>
      </div>
    `);
    await page.addStyleTag({ content: composerCSS + '\n' + roomCSS });
    const input = await page.getByRole('textbox', { name: 'Сообщение' }).boundingBox();
    const bar = await page.locator('.composer__bar').boundingBox();
    expect(input).not.toBeNull();
    expect(bar).not.toBeNull();
    expect(input.width, `Input squeezed at ${width}px`).toBeGreaterThan(105);
    // The duplicated "Root · You are here" strip is no longer rendered on
    // mobile: the space header already owns online presence.
    await expect(page.locator('.live-presence')).toBeHidden();
    const controls = await page.locator('.composer__bar .icon-btn').all();
    for (const control of controls) {
      const box = await control.boundingBox();
      // Browser layout uses subpixel floats (Firefox: 44.000015px).
      expect(box.width).toBeCloseTo(44, 2);
      expect(box.height).toBeCloseTo(44, 2);
    }
    const last = await controls.at(-1).boundingBox();
    expect(last.x + last.width).toBeLessThanOrEqual(width + 1);
  }
});
