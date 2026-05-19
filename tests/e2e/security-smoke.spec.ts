import { expect, loginViaApi, requireCreds, test } from './fixtures';

test.describe('security smoke', () => {
  test('private endpoints reject anonymous callers', async ({ playwright }) => {
    const anonymous = await playwright.request.newContext({
      baseURL: process.env.NEXUS_BASE_URL ?? 'https://nexusosint.uk',
    });
    const probes = [
      { method: 'get', path: '/api/me' },
      { method: 'get', path: '/api/admin/stats' },
      { method: 'get', path: '/api/admin/logs/1' },
      { method: 'get', path: '/health/memory' },
      { method: 'get', path: '/api/spiderfoot/status' },
      { method: 'post', path: '/api/search', data: { query: 'ab' } },
      { method: 'post', path: '/api/victims/search', data: { q: 'ab' } },
    ] as const;

    try {
      for (const probe of probes) {
        const response = probe.method === 'get'
          ? await anonymous.get(probe.path)
          : await anonymous.post(probe.path, { data: probe.data });
        expect([401, 403], `${probe.method.toUpperCase()} ${probe.path}`).toContain(response.status());
      }
    } finally {
      await anonymous.dispose();
    }
  });

  test('normal user cannot access admin-only APIs', async ({ page }) => {
    const { user, pass } = requireCreds();
    await loginViaApi(page, user, pass);

    for (const path of [
      '/health/memory',
      '/api/admin/stats',
      '/api/admin/logs?limit=1',
      '/api/admin/logs/1',
      '/api/admin/users',
      '/api/admin/breach-extra-keys',
    ]) {
      const response = await page.request.get(path);
      expect(response.status(), path).toBe(403);
    }
  });

  test('SpiderFoot status does not expose internal diagnostics', async ({ page }) => {
    const { user, pass } = requireCreds();
    await loginViaApi(page, user, pass);

    const response = await page.request.get('/api/spiderfoot/status');
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body).toHaveProperty('available');
    expect(body).not.toHaveProperty('url');
    expect(body).not.toHaveProperty('error');
  });

  test('security headers are present and CSP blocks inline script policy', async ({ request }) => {
    const response = await request.get('/');
    expect(response.status()).toBe(200);
    const headers = response.headers();

    expect(headers['content-security-policy']).toContain("default-src 'self'");
    expect(headers['content-security-policy']).toContain("script-src 'self'");
    expect(headers['content-security-policy']).toContain("frame-ancestors 'none'");
    expect(headers['content-security-policy']).not.toContain("'unsafe-inline'");
    expect(headers['strict-transport-security']).toContain('max-age=31536000');
    expect(headers['x-content-type-options']).toBe('nosniff');
    expect(headers['x-frame-options']).toBe('DENY');
    expect(headers['referrer-policy']).toBe('strict-origin-when-cross-origin');
  });

  test('CORS does not reflect an untrusted origin', async ({ request }) => {
    const response = await request.fetch('/api/me', {
      method: 'OPTIONS',
      headers: {
        Origin: 'https://evil.example',
        'Access-Control-Request-Method': 'GET',
      },
    });
    const allowOrigin = response.headers()['access-control-allow-origin'] ?? '';
    expect(allowOrigin).not.toBe('*');
    expect(allowOrigin).not.toBe('https://evil.example');
  });

  test('benign invalid inputs fail closed without 500', async ({ page }) => {
    const { user, pass } = requireCreds();
    await loginViaApi(page, user, pass);

    const shortSearch = await page.request.post('/api/search', {
      data: { query: 'a' },
    });
    expect(shortSearch.status()).toBe(422);

    const moreBreaches = await page.request.post('/api/search/more-breaches', {
      data: { query: '', cursor: '' },
    });
    expect(moreBreaches.status()).toBe(400);

    const traversal = await page.request.get('/api/victims/%2e%2e/manifest');
    expect(traversal.status()).not.toBe(200);
    expect(traversal.status()).not.toBe(500);
  });

  test('login gate smoke probe never returns 5xx', async ({ request }) => {
    const response = await request.post('/api/auth', { data: {} });
    expect(response.status()).toBeLessThan(500);
    if (response.status() === 429) {
      expect(response.headers()['retry-after']).toBeTruthy();
    }
  });
});
