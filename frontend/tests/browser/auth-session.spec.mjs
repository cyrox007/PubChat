import { expect, test } from '@playwright/test';

const PASSWORD = 'BrowserGate-2026!';

const projectHandle = (projectName) => {
  const suffix = Date.now().toString(36);
  const project = projectName.replace(/[^a-z0-9]/gi, '').toLowerCase().slice(0, 10);
  return `pw${project}${suffix}`.slice(0, 30);
};

const assertNoPersistedBearer = async (page) => {
  const persisted = await page.evaluate(() => ({
    accessToken: localStorage.getItem('access_token'),
    sessionToken: sessionStorage.getItem('access_token'),
  }));
  expect(persisted.accessToken).toBeNull();
  expect(persisted.sessionToken).toBeNull();
};

const logout = async (page) => {
  const routeProgress = page.locator('.route-progress');
  await expect(routeProgress).toHaveCount(0);

  const trigger = page.locator('.persona-trigger');
  await expect(trigger).toBeVisible();
  await trigger.focus();
  await trigger.press('Enter');
  await expect(trigger).toHaveAttribute('aria-expanded', 'true');

  const logoutItem = page.getByRole('menuitem', { name: 'Выйти' });
  await expect(logoutItem).toBeVisible();
  await logoutItem.focus();
  await logoutItem.press('Enter');
  await expect(page).toHaveURL(/\/login$/);
};

test('registration, refresh rotation, logout and login survive real browser cookie rules', async ({ page, context }, testInfo) => {
  const pageErrors = [];
  page.on('pageerror', (error) => pageErrors.push(String(error)));

  await page.addInitScript(() => {
    window.__pubchatNotificationPermissionRequests = 0;
    if ('Notification' in window && typeof Notification.requestPermission === 'function') {
      Notification.requestPermission = async () => {
        window.__pubchatNotificationPermissionRequests += 1;
        return Notification.permission;
      };
    }
  });

  const handle = projectHandle(testInfo.project.name);
  const displayName = `Browser ${testInfo.project.name}`;

  await page.goto('/registration');
  await expect(page.getByRole('heading', { name: 'Создайте свой образ' })).toBeVisible();

  await page.getByLabel('Как вас называть?').fill(displayName);
  await page.getByLabel('Уникальный адрес').fill(handle);
  await page.getByRole('button', { name: 'Продолжить' }).click();

  await page.getByLabel('Пароль', { exact: true }).fill(PASSWORD);
  await page.getByLabel('Повторите пароль').fill(PASSWORD);
  await page.getByRole('button', { name: 'Войти в PubChat' }).click();

  await expect(page).toHaveURL(/\/$/);
  await expect(page.locator('.persona-trigger')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Найдите место, куда хочется вернуться' })).toBeVisible();
  await assertNoPersistedBearer(page);

  const refreshCookie = (await context.cookies()).find((item) => item.name === 'refresh_token');
  expect(refreshCookie).toBeTruthy();
  expect(refreshCookie.httpOnly).toBe(true);
  expect(refreshCookie.sameSite).toBe('Lax');

  // Full reload destroys the in-memory access token. The SPA must recover using
  // the HttpOnly refresh cookie plus a newly bootstrapped CSRF header proof.
  const refreshResponse = page.waitForResponse(
    (response) => response.url().includes('/api/identity/v2/refresh') && response.status() === 200,
  );
  await page.reload();
  await refreshResponse;
  await expect(page.locator('.persona-trigger')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Найдите место, куда хочется вернуться' })).toBeVisible();
  await assertNoPersistedBearer(page);

  // Enter a real room through SPA navigation. This guards the mobile regression
  // where the shell stayed visible but the routed room content disappeared
  // until a full page reload.
  const spaceName = `Browser room ${testInfo.project.name} ${Date.now().toString(36)}`;
  await page.getByRole('button', { name: 'Создать пространство' }).first().click();
  await expect(page.getByRole('dialog', { name: 'Создать пространство' })).toBeVisible();
  await page.getByLabel('Название').fill(spaceName);
  await page.getByRole('dialog', { name: 'Создать пространство' })
    .getByRole('button', { name: 'Создать пространство' }).click();

  await expect(page).toHaveURL(/\/spaces\/[^/]+$/);
  await expect(page.getByRole('heading', { name: spaceName })).toBeVisible();
  await expect(page.locator('.route-view-frame')).toHaveCount(1);

  if (testInfo.project.name === 'mobile-chromium') {
    const viewport = await page.evaluate(() => {
      const root = document.documentElement;
      const room = document.querySelector('.space-shell')?.getBoundingClientRect();
      const nav = document.querySelector('.mobile-nav')?.getBoundingClientRect();
      return {
        innerHeight: window.innerHeight,
        scrollHeight: Math.max(root.scrollHeight, document.body.scrollHeight),
        roomBottom: room?.bottom ?? null,
        navTop: nav?.top ?? null,
      };
    });
    expect(viewport.scrollHeight).toBeLessThanOrEqual(viewport.innerHeight + 2);
    expect(viewport.roomBottom).not.toBeNull();
    expect(viewport.navTop).not.toBeNull();
    expect(viewport.roomBottom).toBeLessThanOrEqual(viewport.navTop + 2);
  }

  // Room management stays inside the same mounted conversation, including mobile.
  const composer = page.getByPlaceholder('Сообщение', { exact: true });
  await expect(composer).toBeEnabled();
  await composer.fill('Unsent room draft');
  await page.evaluate(() => { window.__roomConversation = document.querySelector('.conversation-area'); });
  await page.getByRole('button', { name: 'Открыть информацию о пространстве' }).click();
  const roomPanel = page.getByRole('complementary', { name: 'Информация о пространстве' });
  const roomNavigation = roomPanel.getByRole('navigation', { name: 'Навигация пространства' });
  await expect(roomNavigation).toBeVisible();
  await expect(page.locator('.app-shell > .space-context-nav')).toHaveCount(0);
  await roomNavigation.getByRole('link', { name: 'Центр', exact: true }).click();
  await expect(roomPanel.getByPlaceholder('Например: Без личных оскорблений')).toBeVisible();
  await roomPanel.getByPlaceholder('Например: Без личных оскорблений').fill('Browser room rule');
  await roomPanel.getByPlaceholder('Коротко объясните правило и зачем оно нужно').fill('Rule from the room panel');
  await roomPanel.getByRole('button', { name: 'Добавить правило' }).click();
  await expect(roomPanel.getByRole('heading', { name: 'Browser room rule' })).toBeVisible();
  await roomNavigation.getByRole('link', { name: 'Модерация', exact: true }).click();
  await expect(roomPanel.getByRole('button', { name: /Жалобы/ })).toBeVisible();
  expect(await page.evaluate(() => window.__roomConversation === document.querySelector('.conversation-area'))).toBe(true);
  await roomPanel.getByRole('button', { name: 'Закрыть панель' }).click();
  await expect(page).toHaveURL(/\/spaces\/[^/]+$/);
  await expect(composer).toHaveValue('Unsent room draft');

  // Verify a cold deep link in its own page instead of destroying the
  // authenticated room document while it may still have read requests in
  // flight. WebKit can report the normal unload cancellation as a page error
  // ("due to access control checks"), hiding genuine application failures.
  // The second tab shares the real HttpOnly session and must bootstrap itself.
  const roomUrl = page.url();
  const deepLinkPage = await context.newPage();
  const deepLinkErrors = [];
  deepLinkPage.on('pageerror', (error) => deepLinkErrors.push(String(error)));
  await deepLinkPage.goto(`${roomUrl}/moderation`);
  await expect(deepLinkPage.locator('.space-shell')).toBeVisible();
  await expect(deepLinkPage.locator('.space-panel--workspace')).toBeVisible();
  expect(deepLinkErrors).toEqual([]);
  await deepLinkPage.close();

  // Test actual SPA route navigation without tearing down the document:
  // a route switch must preserve auth, realtime lifecycle and the shell.
  const messengerLink = page.locator('a[href="/messenger"]:visible').first();
  await expect(messengerLink).toBeVisible();
  await messengerLink.click();
  await expect(page).toHaveURL(/\/messenger$/);
  await expect(page.locator('a[href="/messenger"]:visible').first()).toBeVisible();

  // Friendship Hub: the native and Web clients share the same Account-based
  // friend-request contract. Verify authenticated navigation and all three
  // consent states without relying on synthetic server responses.
  const peopleLink = page.locator('a[href="/people"]:visible').first();
  await peopleLink.click();
  await expect(page).toHaveURL(/\\/people$/);
  await page.getByRole('link', { name: 'Друзья и заявки' }).click();
  await expect(page).toHaveURL(/\\/friends$/);
  await expect(page.getByRole('heading', { name: 'Друзья и заявки' })).toBeVisible();
  const socialNav = page.getByRole('navigation', { name: 'Разделы дружбы' });
  await socialNav.getByRole('button', { name: 'Исходящие' }).click();
  await socialNav.getByRole('button', { name: 'Друзья', exact: true }).click();
  await socialNav.getByRole('button', { name: 'Входящие' }).click();
  await expect(socialNav.getByRole('button', { name: 'Входящие' })).toHaveAttribute('aria-current', 'page');

  // Browser defaults differ in headless environments, so permission state is not
  // a reliable prompt signal. Count direct requestPermission calls instead.
  const permissionRequests = await page.evaluate(
    () => window.__pubchatNotificationPermissionRequests || 0,
  );
  expect(permissionRequests).toBe(0);

  await logout(page);
  expect((await context.cookies()).some((item) => item.name === 'refresh_token')).toBe(false);
  await assertNoPersistedBearer(page);

  // Login itself is another unsafe request and must work without relying on a
  // mount-time race for CSRF bootstrap.
  await page.getByLabel('Логин или email').fill(handle);
  await page.getByLabel('Пароль').fill(PASSWORD);
  await page.getByRole('button', { name: 'Войти' }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.locator('.persona-trigger')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Найдите место, куда хочется вернуться' })).toBeVisible();
  await assertNoPersistedBearer(page);

  expect(pageErrors).toEqual([]);
});
