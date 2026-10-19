import { expect, test } from '@playwright/test';

// Reported defect at ~1687px: the radial auth background stopped at the
// max-width .container edge, leaving dark vertical bands at the sides.
test('login and registration artwork fill the viewport without side gutters', async ({ page }) => {
  for (const width of [360, 1280, 1687, 1920]) {
    await page.setViewportSize({ width, height: 900 });
    for (const route of ['/login', '/registration']) {
      await page.goto(route);
      const screen = page.locator('main.auth-screen');
      await expect(screen).toBeVisible();
      await expect(page.locator('main')).toHaveCount(1);
      await expect(page.locator('.app-content--auth')).toHaveCount(1);
      await expect(page.locator('.auth-screen .auth-ambient')).toHaveCount(0);

      const rects = await page.evaluate(() => {
        const root = document.documentElement;
        const content = document.querySelector('.app-content--auth');
        const screen = document.querySelector('.auth-screen');
        const card = document.querySelector('.auth-card');
        const authBox = screen.getBoundingClientRect();
        const contentBox = content.getBoundingClientRect();
        const cardBox = card.getBoundingClientRect();
        const css = getComputedStyle(screen);
        return {
          viewportWidth: root.clientWidth,
          viewportHeight: window.innerHeight,
          scrollWidth: Math.max(root.scrollWidth, document.body.scrollWidth),
          authLeft: authBox.left,
          authRight: authBox.right,
          authBottom: authBox.bottom,
          contentLeft: contentBox.left,
          contentRight: contentBox.right,
          cardLeft: cardBox.left,
          cardRight: cardBox.right,
          backgroundColor: css.backgroundColor,
          backgroundImage: css.backgroundImage,
        };
      });

      expect(Math.abs(rects.authLeft), `${route} background starts at x=${rects.authLeft} for ${width}px`).toBeLessThanOrEqual(1);
      expect(Math.abs(rects.authRight - rects.viewportWidth), `${route} background ends at x=${rects.authRight} for ${width}px`).toBeLessThanOrEqual(1);
      expect(Math.abs(rects.contentLeft)).toBeLessThanOrEqual(1);
      expect(Math.abs(rects.contentRight - rects.viewportWidth)).toBeLessThanOrEqual(1);
      expect(rects.authBottom, 'Auth gradient must reach the bottom of the window').toBeGreaterThanOrEqual(rects.viewportHeight - 1);
      expect(rects.scrollWidth, 'Auth must not introduce horizontal page scrolling').toBeLessThanOrEqual(rects.viewportWidth + 1);
      expect(rects.backgroundImage).toContain('radial-gradient(');
      expect(rects.backgroundColor).not.toBe('rgba(0, 0, 0, 0)');
      expect(rects.cardLeft).toBeGreaterThanOrEqual(0);
      expect(rects.cardRight).toBeLessThanOrEqual(rects.viewportWidth + 1);
    }
  }
});
