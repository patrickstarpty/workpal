import assert from 'node:assert/strict';
import { chromium, expect } from '@playwright/test';
import { createServer } from '../server/api.mjs';
const server = createServer({ dbPath: ':memory:' });
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const base = `http://127.0.0.1:${server.address().port}`;
let browser;
try {
  browser = await chromium.launch();
  for (const width of [1440, 390, 320]) {
    const page = await browser.newPage({ viewport: { width, height: 900 } });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base);
    await expect(page.getByRole('heading', { name: 'Workpal', exact: true })).toBeVisible();
    await expect(page).toHaveTitle('Welcome · Workpal');
    await expect(page).toHaveURL(/#\/landing$/);
    await expect(page.getByText('Let’s work together.')).toBeVisible();
    await page.screenshot({path: '/tmp/workpal-login-'+width+'.png'});
    await expect(page.locator('[data-mc="app-rail"]')).toHaveCount(0);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    const background = await page.request.get(base + '/images/welcome-celebration-restored.png');
    assert.equal(background.status(), 200);
    await page.getByRole('link', { name: 'Enter Workpal' }).focus();
    await page.keyboard.press('Enter');
    await expect(page).toHaveURL(/#\/review\/projects$/);
    await expect(page.locator('[data-mc="page"]')).toBeVisible();
    if (width === 1440) {
      const ask = page.locator('[data-chat-anchor="new"]');
      await expect(ask).toHaveAccessibleName('Ask Workpal');
      await expect(ask.locator('strong')).toHaveText('Workpal');
      await expect(ask.locator('strong')).toHaveCSS('font-style', 'italic');
      await expect(ask.locator('strong')).toHaveCSS('font-weight', '700');
      await expect(ask.locator('svg image')).toHaveCount(1);
      assert.equal(await ask.evaluate(el => el.firstElementChild.tagName.toLowerCase()), 'svg');
      await ask.click();
      await expect(ask).toHaveAttribute('aria-pressed', 'true');
    }
    await page.goBack();
    await expect(page.getByRole('link', { name: 'Enter Workpal' })).toBeVisible();
    await page.goto(base + '/#/landing');
    await expect(page.getByRole('link', { name: 'Enter Workpal' })).toBeVisible();
    await page.goto(base + '/#/review/projects');
    await expect(page.locator('[data-mc="page"]')).toBeVisible();
    assert.deepEqual(errors, []);
    await page.close();
  }
  console.log('PASS: login entry, background, keyboard entry, history, deep links, responsive layout and branded chat button');
} finally {
  await browser?.close();
  await new Promise(resolve => { server.close(resolve); server.closeAllConnections(); });
}
