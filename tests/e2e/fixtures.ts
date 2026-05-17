import { APIResponse, Page, test as base, expect } from '@playwright/test';

export const TEST_USER = process.env.NEXUS_TEST_USER;
export const TEST_PASS = process.env.NEXUS_TEST_PASS;

export function requireCreds(): { user: string; pass: string } {
  if (!TEST_USER || !TEST_PASS) {
    throw new Error(
      'NEXUS_TEST_USER and NEXUS_TEST_PASS must be set in the environment. ' +
        'Never hardcode credentials. See tests/e2e/README.md.',
    );
  }
  return { user: TEST_USER, pass: TEST_PASS };
}

export async function loginViaApi(page: Page, user: string, pass: string): Promise<APIResponse> {
  const res = await page.request.post('/api/login', {
    headers: { 'Content-Type': 'application/json' },
    data: { username: user, password: pass },
  });
  expect(res.status(), 'login returns 200').toBe(200);
  const body = await res.json();
  expect(body.ok).toBe(true);

  const setCookie = res.headers()['set-cookie'] ?? '';
  const match = /(?:^|,\s*)nx_session=([^;]+)/.exec(setCookie);
  if (match) {
    await page.context().addCookies([{
      name: 'nx_session',
      value: match[1],
      url: process.env.NEXUS_BASE_URL ?? 'https://nexusosint.uk',
      httpOnly: true,
      secure: true,
      sameSite: 'Strict',
    }]);
  }

  return res;
}

export async function loginViaUi(page: Page, user: string, pass: string): Promise<APIResponse> {
  await page.goto('/');
  await expect(page.locator('#authScreen')).toBeVisible();
  await page.fill('#authUsername', user);
  await page.fill('#authInput', pass);
  const [res] = await Promise.all([
    page.waitForResponse((r) => r.url().endsWith('/api/login')),
    page.click('#authBtn'),
  ]);
  return res;
}

export async function assertNoSessionSecretsInWebStorage(page: Page): Promise<void> {
  const storage = await page.evaluate(() => ({
    local: Object.entries(localStorage),
    session: Object.entries(sessionStorage),
  }));
  const serialized = JSON.stringify(storage).toLowerCase();
  expect(serialized).not.toContain('nx_session');
  expect(serialized).not.toContain('bearer ');
  expect(serialized).not.toContain('access_token');
  expect(serialized).not.toContain('refresh_token');
  expect(serialized).not.toContain('id_token');
  expect(serialized).not.toContain('eyjhb');
}

export const test = base;
export { expect };
