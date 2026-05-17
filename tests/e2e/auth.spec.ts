import {
  assertNoSessionSecretsInWebStorage,
  expect,
  loginViaApi,
  requireCreds,
  test,
} from './fixtures';

test.describe('auth flow', () => {
  test('logs in, opens dashboard, and logs out', async ({ page }) => {
    const { user, pass } = requireCreds();

    await page.goto('/');
    await expect(page.locator('#authScreen')).toBeVisible();

    const loginResponse = await loginViaApi(page, user, pass);

    const setCookie = loginResponse.headers()['set-cookie'] ?? '';
    expect(setCookie).toContain('nx_session=');
    expect(setCookie).toContain('HttpOnly');
    expect(setCookie).toContain('Secure');
    expect(setCookie).toContain('SameSite=strict');

    await page.reload();
    await expect(page.locator('#app')).toBeVisible();
    await expect(page.locator('#navUserName')).toHaveText(user);
    await assertNoSessionSecretsInWebStorage(page);

    await page.locator('#navUserTrigger').click();
    const [logoutResponse] = await Promise.all([
      page.waitForResponse((r) => r.url().endsWith('/api/logout')),
      page.locator('[data-action="sign-out"]').click(),
    ]);
    expect(logoutResponse.status()).toBe(200);
    await expect(page.locator('#authScreen')).toBeVisible();

    const me = await page.request.get('/api/me');
    expect(me.status()).toBe(401);
  });

  test('non-admin test user cannot load admin page shell', async ({ page }) => {
    const { user, pass } = requireCreds();
    await loginViaApi(page, user, pass);

    const me = await page.request.get('/api/me');
    expect(me.status()).toBe(200);
    expect(await me.json()).toMatchObject({ username: user, role: 'user' });

    const admin = await page.request.get('/admin', { maxRedirects: 0 });
    expect([303, 403]).toContain(admin.status());
    if (admin.status() === 303) {
      expect(admin.headers().location).toBe('/');
    }
  });
});
