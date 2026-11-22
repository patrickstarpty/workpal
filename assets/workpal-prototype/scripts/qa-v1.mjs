import { createRequire } from 'node:module';
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
const require = createRequire(import.meta.url);
const { chromium, expect } = require(process.env.WORKPAL_PLAYWRIGHT || '@playwright/test');
const root = resolve(import.meta.dirname, '..');
await mkdir(resolve(root, 'test-results'), { recursive: true });
const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
const page = await context.newPage();
const errors = [];
const results = [];
page.on('pageerror', error => errors.push(error.message));
const base = pathToFileURL(resolve(root, 'review-v1.html')).href;
async function visit(route) { await page.goto(`${base}#${route}`); await expect(page.locator('main h1')).toBeVisible(); }
async function check(name, fn) { await fn(); results.push(name); console.log(`PASS ${name}`); }
try {
  await check('All ten pages render at desktop and mobile widths without overflow', async () => {
    for (const width of [1440, 1024, 390]) {
      await page.setViewportSize({ width, height: width === 390 ? 844 : 1000 });
      for (const route of ['overview', 'stats', 'projects', 'workflow', 'tasks', 'agents', 'skills', 'experiments', 'research', 'settings']) {
        await visit(route);
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
        if (overflow) throw new Error(`${route} overflows at ${width}px`);
        if (width !== 1024) await page.screenshot({ path: resolve(root, `test-results/${route}-${width === 390 ? 'mobile' : 'desktop'}.png`), fullPage: true, animations: 'disabled' });
      }
    }
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await check('Task creation, safe text rendering, status update and persistence', async () => {
    await visit('tasks');
    await page.locator('.heading-actions [data-action="new-task"]').click();
    const title = 'QA <img src=x onerror=alert(1)> 引用校验';
    await page.locator('[name="title"]').fill(title);
    await page.locator('[name="description"]').fill('用于检查任务输入是否作为文字显示。');
    await page.locator('[name="checks"]').fill('显示完整文本\n状态能够保存');
    await page.locator('#new-task-form button[type="submit"]').click();
    const task = page.locator('.task-card').filter({ hasText: title });
    await expect(task).toBeVisible();
    await expect(page.locator('.task-card img')).toHaveCount(0);
    await task.click();
    await page.locator('#task-form [name="status"]').selectOption('done');
    await page.locator('#task-form button[type="submit"]').click();
    await page.reload();
    await expect(page.locator('.kanban-column').filter({ has: page.getByRole('heading', { name: '已完成', exact: true }) }).locator('.task-card').filter({ hasText: title })).toHaveCount(1);
    await page.locator('#task-search').fill('no-such-task');
    await expect(page.locator('.task-card')).toHaveCount(0);
    await expect(page.locator('#task-count')).toHaveText('0');
  });
  await check('Skill search, empty state, category, bookmark and detail links', async () => {
    await visit('skills');
    await page.locator('#skill-search').fill('Playwright');
    await expect(page.locator('.skill-card')).toHaveCount(1);
    await expect(page.locator('.skill-card h2')).toHaveText('Webapp Testing');
    await page.locator('#skill-search').fill('no-such-skill');
    await expect(page.locator('.empty-state')).toBeVisible();
    await page.locator('[data-action="reset-skills"]').click();
    await page.locator('[data-action="category"][data-category="知识与协作"]').click();
    await expect(page.locator('.skill-card')).toHaveCount(1);
    await page.locator('[data-action="bookmark"][data-id="skill-creator"]').click();
    await page.reload();
    await expect(page.locator('[data-action="bookmark"][data-id="skill-creator"]')).toHaveAttribute('aria-pressed', 'true');
    await visit('skills?id=brainstorming');
    await expect(page.locator('dialog')).toBeVisible();
    await expect(page.locator('dialog a[target="_blank"]')).toHaveAttribute('href', /github.com\/obra\/superpowers/);
    await page.keyboard.press('Escape');
    await expect(page.locator('dialog')).not.toBeVisible();
  });
  await check('Review notes persist safely and export; reset preserves review notes', async () => {
    await visit('research');
    await page.locator('.heading-actions [data-action="review"]').click();
    await page.locator('[name="author"]').fill('导师审阅');
    await page.locator('[name="text"]').fill('请明确人工介入的定义 <script>alert(1)</script>');
    await page.locator('#review-form button[type="submit"]').click();
    await expect(page.locator('.review-note')).toContainText('请明确人工介入的定义');
    await expect(page.locator('.review-note script')).toHaveCount(0);
    const downloadPromise = page.waitForEvent('download');
    await page.locator('dialog [data-action="export-review"]').click();
    const download = await downloadPromise;
    if (!download.suggestedFilename().includes('审阅记录')) throw new Error('Wrong export name');
    await page.keyboard.press('Escape');
    await visit('settings');
    await page.locator('[data-action="reset-data"]').click();
    await page.locator('[data-action="confirm-reset"]').click();
    await page.reload();
    await expect(page.locator('.settings-panel')).toContainText('已记录 1 条审阅意见');
  });
  await check('Human gates advance through all six stages and finish the demonstration', async () => {
    await visit('workflow');
    await page.locator('[data-action="reset-flow"]').click();
    for (let i = 0; i < 6; i++) await page.locator('.gate [data-action="approve-stage"]').click();
    await expect(page.locator('.flow-node.completed')).toHaveCount(6);
    await expect(page.locator('.gate')).toContainText('已确认');
    await expect(page.locator('.heading-actions')).toContainText('重新演示');
  });
  await check('Global search, keyboard dialog dismissal, mobile navigation and skip link', async () => {
    await page.keyboard.press('Meta+k');
    await page.locator('#global-search').fill('Skill Hub');
    await page.locator('.search-result[data-action="navigate"][data-id="skills"]').click();
    await expect(page.locator('main h1')).toContainText('好方法');
    await page.locator('.skip-link').focus();
    await page.keyboard.press('Enter');
    await expect(page.locator('main')).toBeFocused();
    await expect(page.locator('main h1')).toContainText('好方法');
    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator('[data-action="mobile-nav"]').click();
    await page.locator('.sidebar nav a[href="#research"]').click();
    await expect(page.locator('main h1')).toContainText('让人机协作');
    await expect(page.locator('.app-shell')).not.toHaveClass(/nav-open/);
  });
  if (errors.length) throw new Error(`Browser errors: ${errors.join('\n')}`);
  await writeFile(resolve(root, 'test-results/qa.json'), JSON.stringify({ status: 'passed', checks: results, browserErrors: errors }, null, 2));
  console.log(`${results.length} browser checks passed; screenshots and report in test-results/.`);
} finally { await browser.close(); }
