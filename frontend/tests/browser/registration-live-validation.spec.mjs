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
  await email.fill('first.last+tag@example.com');
  await expect(page.getByText('✓ Формат email корректен')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Войти в PubChat' })).toBeEnabled();

  await email.fill('not-an-email');
  await expect(page.getByText('Проверьте формат email')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Войти в PubChat' })).toBeDisabled();

  await email.fill('');
  await expect(page.getByRole('button', { name: 'Войти в PubChat' })).toBeEnabled();

  expect(runtimeErrors).toEqual([]);
});
