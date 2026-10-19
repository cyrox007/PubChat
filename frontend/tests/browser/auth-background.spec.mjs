import { expect, test } from '@playwright/test';

// Protect the actual routed login/registration views. Previously App.vue wrapped
// every view in .container (max-width: 1680px), so the auth gradient ended at
// the container edges and exposed vertical strips of the body background.
test('auth gradient fills viewport without constrained-container side bands', async ({ page }) => {
  for (const width of [320, 390, 1440, 1920]) {
    await page.setViewportSize({ width, height: 900 });
    for (const path of ['/login', '/registration']) {
      await page.goto(path);
      const screen = page.locator('.auth-screen');
      const card = page.locator('.auth-card');
      await expect(screen).toBeVisible();
      await expect(card).toBeVisible();
      await expect(page.locator('main')).toHaveCount(1);

      const geometry = await page.evaluate(() => {
        const auth = document.querySelector('.auth-screen');
        const shell = document.querySelector('.app-shell');
        const content = document.querySelector('.app-content');
        const card = document.querySelector('.auth-card');
        const rect = auth.getBoundingClientRect();
        const cardRect = card.getBoundingClientRect();
        return {
          screenLeft: rect.left,
          screenRight: rect.right,
          screenBottom: rect.bottom,
          cardCenter: cardRect.left + cardRect.width / 2,
          viewportWidth: window.innerWidth,
          viewportHeight: window.innerHeight,
          scrollWidth: document.documentElement.scrollWidth,
          isGuestLayout: shell.classList.contains('app-shell--auth') &&
            content.classList.contains('app-content--auth'),
          gradient: getComputedStyle(auth).backgroundImage,
        };
      });
      expect(geometry.isGuestLayout, `${path} missing full-bleed layout`).toBe(true);
      expect(Math.abs(geometry.screenLeft), `left strip on ${path}, ${width}px`).toBeLessThanOrEqual(1);
      expect(Math.abs(geometry.screenRight - geometry.viewportWidth), `right strip on ${path}, ${width}px`).toBeLessThanOrEqual(1);
      expect(geometry.screenBottom, `auth background ends above the viewport`).toBeGreaterThanOrEqual(geometry.viewportHeight - 1);
      expect(geometry.scrollWidth, `horizontal overflow at ${width}px`).toBeLessThanOrEqual(geometry.viewportWidth + 1);
      expect(Math.abs(geometry.cardCenter - geometry.viewportWidth / 2), 'card must remain centered').toBeLessThanOrEqual(2);
      expect(geometry.gradient).toContain('radial-gradient');
    }
  }
});
