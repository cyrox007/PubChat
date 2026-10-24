import { expect, test } from '@playwright/test';

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
  await expect(page.getByText('Проверяем, свободен ли email…')).toBeVisible();
  // Exercises real Identity v2 + Redis lookup instead of mocking a success.
  await expect(page.getByText('✓ Email предварительно свободен')).toBeVisible({ timeout: 15000 });
  await expect(page.getByRole('button', { name: 'Войти в PubChat' })).toBeEnabled();

  await email.fill('not-an-email');
  await expect(page.getByText('Проверьте формат email.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Войти в PubChat' })).toBeDisabled();

  // Known-taken and network-limit responses must not flash 'available'.
  await page.route('**/api/identity/v2/email-availability', async (route) => {
    const body = route.request().postDataJSON();
    if (body.email === 'already-used@example.com') {
      await route.fulfill({ status: 200, contentType: 'application/json',
        body: JSON.stringify({ available: false }) });
    } else if (body.email === 'rate-limited@example.com') {
      await route.fulfill({ status: 429, contentType: 'application/json',
        body: JSON.stringify({ detail: { error_type: 'email_preflight_rate_limited' } }) });
    } else {
      await route.continue();
    }
  });
  await email.fill('already-used@example.com');
  await expect(page.getByText('Этот email уже используется другим аккаунтом.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Войти в PubChat' })).toBeDisabled();
  await email.fill('rate-limited@example.com');
  await expect(page.getByText('Слишком много проверок. Повторите позднее или продолжите регистрацию.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Войти в PubChat' })).toBeEnabled();

  await email.fill('');
  await expect(page.getByText('Можно оставить пустым и добавить позже.')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Войти в PubChat' })).toBeEnabled();

  expect(runtimeErrors).toEqual([]);
});
