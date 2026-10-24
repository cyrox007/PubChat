import { expect, test, request } from '@playwright/test';

/**
 * Real-browser regression for the two registration issues reported on 24 Oct:
 * - username availability never resolves
 * - all ordinary email addresses appear invalid
 * Browser CI starts the actual Identity v2 backend and SPA behind /api.
 */
test('registration confirms username and accepts normal optional email', async ({ page }, testInfo) => {
  const runtimeErrors = [];
  page.on('pageerror', (error) => runtimeErrors.push(String(error)));

  const handle = (`qaweb${testInfo.project.name.replace(/[^a-z0-9]/gi, '').slice(0, 8)}${Date.now().toString(36)}`)
    .toLowerCase().slice(0, 32);

  // Seed a genuinely occupied email in an isolated API cookie jar. The
  // registration page remains unauthenticated while the backend stores the
  // credential and enforces its unique constraint.
  const api = await request.newContext({
    baseURL: process.env.PUBCHAT_BROWSER_BASE_URL || 'http://127.0.0.1:4173',
  });
  const csrfResponse = await api.get('/api/csrf/get');
  expect(csrfResponse.ok()).toBeTruthy();
  const { csrf_token: csrfToken } = await csrfResponse.json();
  const occupiedEmail = `occupied-${handle}@example.com`;
  const occupied = await api.post('/api/identity/v2/register', {
    headers: { 'X-CSRF-Token': csrfToken },
    data: { handle: (`used${handle}`).slice(0, 32),
      display_name: 'Occupied email fixture',
      password: 'BrowserGate-2026!', email: occupiedEmail, social_intent: 'open' },
  });
  expect(occupied.status(), await occupied.text()).toBe(201);
  await api.dispose();

  await page.goto('/registration');
  await expect(page.getByRole('heading', { name: 'Создайте свой образ' })).toBeVisible();
  await page.getByLabel('Как вас называть?').fill('Регрессия формы');
  await page.getByLabel('Уникальный адрес').fill(handle);
  await expect(page.getByText('✓ Username предварительно свободен')).toBeVisible({ timeout: 15000 });

  await page.getByRole('button', { name: 'Продолжить' }).click();
  await expect(page.getByLabel('Пароль', { exact: true })).toBeVisible();
  await page.getByLabel('Пароль', { exact: true }).fill('StrongExample2026!');
  await page.getByLabel('Повторите пароль').fill('StrongExample2026!');

  const email = page.locator('input[type="email"]');
  const uniqueEmail = `${handle}@example.com`;
  await email.fill(uniqueEmail);
  // Exercises real Identity v2 + Redis lookup instead of mocking a success.
  await expect(page.getByText('✓ Email предварительно свободен')).toBeVisible({ timeout: 15000 });
  await expect(page.getByRole('button', { name: 'Войти в PubChat' })).toBeEnabled();

  await email.fill('not-an-email');
  await expect(page.getByText('Проверьте формат email.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Войти в PubChat' })).toBeDisabled();

  // This must query the same Identity v2 database, not a mocked response.
  await email.fill(occupiedEmail);
  await expect(page.getByText('Этот email уже используется другим аккаунтом.'))
    .toBeVisible({ timeout: 15000 });
  await expect(page.getByRole('button', { name: 'Войти в PubChat' })).toBeDisabled();

  await email.fill('');
  await expect(page.getByText('Можно оставить пустым и добавить позже.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Войти в PubChat' })).toBeEnabled();

  expect(runtimeErrors).toEqual([]);
});
