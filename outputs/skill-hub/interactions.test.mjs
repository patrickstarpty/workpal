import { readFile } from 'node:fs/promises';
import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { chromium } from '@playwright/test';

const html = await readFile(new URL('../workpal-capability-hub.html', import.meta.url), 'utf8');
const catalog = JSON.parse(await readFile(new URL('./catalog.json', import.meta.url), 'utf8'));
let browser;
before(async () => { browser = await chromium.launch({ headless: true }); });
after(async () => { await browser?.close(); });

async function withPage(run) {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  try {
    await page.setContent(html);
    await run(page);
    assert.deepEqual(errors, []);
  } finally { await page.close(); }
}

test('search preserves sequential typing, mid-string editing and the input node', () => withPage(async page => {
  await page.locator('.nav [data-nav="skills"]').click();
  const search = page.getByRole('searchbox', { name: 'Search skills' });
  const original = await search.elementHandle();
  await search.pressSequentially('code');
  assert.equal(await search.inputValue(), 'code');
  assert.ok(await original.evaluate(node => node === document.activeElement));
  await search.press('ArrowLeft');
  await search.press('ArrowLeft');
  await search.pressSequentially('X');
  assert.equal(await search.inputValue(), 'coXde');
  assert.equal(await search.evaluate(node => node.selectionStart), 3);
  await search.press('Backspace');
  await search.press('Shift+ArrowLeft');
  await search.pressSequentially('a');
  assert.equal(await search.inputValue(), 'cade');
  assert.equal(await search.evaluate(node => node.selectionStart), 2);
}));

test('search leaves IME composition intact and filters after commit', () => withPage(async page => {
  await page.locator('.nav [data-nav="skills"]').click();
  const search = page.getByRole('searchbox', { name: 'Search skills' });
  await search.focus();
  const original = await search.elementHandle();
  const initialCount = await page.locator('.catalog-count').innerText();
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Input.imeSetComposition', { text: '测', selectionStart: 1, selectionEnd: 1 });
  assert.ok(await original.evaluate(node => node.isConnected && node === document.activeElement));
  assert.equal(await page.locator('.catalog-count').innerText(), initialCount);
  await cdp.send('Input.imeSetComposition', { text: '测试', selectionStart: 2, selectionEnd: 2 });
  await cdp.send('Input.insertText', { text: '测试' });
  assert.equal(await search.inputValue(), '测试');
  assert.ok(await original.evaluate(node => node.isConnected && node === document.activeElement));
  assert.equal(await page.locator('.catalog-count').innerText(), '0 of 203 entries');
}));

test('a lower-list skill opens visible focused details and returns to its card', () => withPage(async page => {
  await page.locator('.nav [data-nav="skills"]').click();
  await page.getByRole('button', { name: 'Show more' }).click();
  const card = page.locator('[data-skill]').last();
  const id = await card.getAttribute('data-skill');
  await card.click();
  const detail = page.locator('.selection h2');
  const box = await detail.boundingBox();
  assert.ok(box.y >= 0 && box.y + box.height <= 844, `Detail outside viewport: ${JSON.stringify(box)}`);
  assert.ok(await detail.evaluate(node => node === document.activeElement));
  await page.getByRole('button', { name: 'Back to skills' }).click();
  const returned = page.locator('[data-skill]').filter({ hasText: catalog.skills.find(s => s.id === id).name }).last();
  assert.equal(await page.evaluate(() => document.activeElement.dataset.skill), id);
  const returnedBox = await returned.boundingBox();
  assert.ok(returnedBox.y >= 0 && returnedBox.y < 844);
  await page.keyboard.press('Enter');
  assert.ok(await page.locator('.selection h2').evaluate(node => node === document.activeElement));
}));

test('every Overview skill resolves by its visible name and opens the same catalog entry', () => withPage(async page => {
  for (let stage = 0; stage < 6; stage++) {
    await page.locator('.nav [data-nav="overview"]').click();
    await page.locator('.stages [data-stage="'+stage+'"]').click();
    const names = await page.locator('.facts .chips .chip').allTextContents();
    for (const name of names) {
      assert.ok(catalog.skills.some(s => s.name === name), `Unknown Overview skill: ${name}`);
      const chip = page.locator('.facts .chips button').filter({ hasText: name });
      const id = await chip.getAttribute('data-open-skill');
      assert.ok(catalog.skills.some(s => s.id === id && s.name === name));
      await chip.click();
      assert.equal(await page.locator('.selection h2').innerText(), name);
      assert.ok(await page.locator('.selection h2').evaluate(node => node === document.activeElement));
      await page.getByRole('searchbox', { name: 'Search skills' }).fill(name);
      assert.ok((await page.locator('.catalog-count').innerText()).startsWith('0 ') === false);
      await page.locator('.nav [data-nav="overview"]').click();
      await page.locator('.stages [data-stage="'+stage+'"]').click();
    }
  }
}));

test('global squads drill into composition, roles and skills with a focused return path', () => withPage(async page => {
  await page.locator('.nav [data-nav="team"]').click();
  assert.equal(await page.locator('.squad-card').count(), 4);
  assert.equal(await page.locator('.shared-pool [data-agent]').count(), 4);
  assert.equal(await page.locator('.agent-profile').count(), 0);
  for (const id of ['discovery', 'delivery', 'assurance', 'operations']) {
    await page.locator('[data-squad="'+id+'"]').click();
    assert.ok(await page.locator('#squad-title').evaluate(node => node === document.activeElement));
    const members = page.locator('.squad-members [data-agent]');
    assert.ok(await members.count());
    const roleId = await members.first().getAttribute('data-agent');
    await members.first().click();
    assert.ok(await page.locator('#agent-title').evaluate(node => node === document.activeElement));
    await page.locator('[data-role-back]').click();
    assert.equal(await page.evaluate(() => document.activeElement.dataset.agent), roleId);
    await page.locator('[data-squad-back]').click();
    assert.equal(await page.evaluate(() => document.activeElement.dataset.squad), id);
  }
  await page.locator('.shared-pool [data-agent="verifier"]').click();
  await page.locator('[data-open-skill="gstack:qa-only/SKILL.md"]').click();
  assert.equal(await page.locator('.selection h2').innerText(), 'qa-only');
  assert.ok(await page.locator('.selection h2').evaluate(node => node === document.activeElement));
  await page.locator('.nav [data-nav="team"]').click();
  await page.locator('[data-related-agent="implementation"]').click();
  assert.ok(await page.locator('#agent-title').evaluate(node => node === document.activeElement));
  await page.locator('[data-role-back]').click();
  assert.equal(await page.evaluate(() => document.activeElement.dataset.agent), 'verifier');
  await page.locator('[data-squad="delivery"]').click();
  await page.locator('.squad-handoffs [data-squad]').first().click();
  assert.ok(await page.locator('#squad-title').evaluate(node => node === document.activeElement));
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
}));

test('each capability page leads with an accurate interactive chart', () => withPage(async page => {
  assert.ok(await page.locator('#page > :first-child').evaluate(n => n.classList.contains('cap-chart')));
  await page.locator('[data-chart-stage="3"]').click();
  assert.equal(await page.locator('.stages [aria-pressed="true"]').innerText(), 'Test');
  await page.locator('.nav [data-nav="skills"]').click();
  assert.ok(await page.locator('#page > :first-child').evaluate(n => n.classList.contains('cap-chart')));
  const bars = await page.locator('[data-chart-type]').evaluateAll(nodes => nodes.map(n => ({id:n.dataset.chartType,total:Number(n.dataset.total),parts:[...n.querySelectorAll('[data-source]')].map(p=>({source:p.dataset.source,count:Number(p.dataset.count)}))})));
  assert.equal(bars.length, catalog.types.length);
  for (const bar of bars) {
    assert.equal(bar.total, catalog.skills.filter(s=>s.types.includes(bar.id)).length);
    for (const part of bar.parts) assert.equal(part.count, catalog.skills.filter(s=>s.types.includes(bar.id)&&s.id.startsWith(part.source+':')).length);
  }
  await page.locator('[data-chart-type="quality"]').click();
  assert.equal(await page.locator('#skill-type').inputValue(), 'quality');
  assert.ok(await page.locator('#skill-type').evaluate(n=>n===document.activeElement));
  await page.locator('.nav [data-nav="team"]').click();
  assert.ok(await page.locator('#page > :first-child').evaluate(n => n.classList.contains('cap-chart')));
  await page.locator('[data-chart-squad="delivery"]').first().click();
  assert.equal(await page.locator('#squad-title').innerText(), 'Engineering delivery');
  await page.locator('[data-squad-back]').click();
  assert.equal(await page.evaluate(()=>document.activeElement.dataset.chartSquad), 'delivery');
  await page.locator('[data-chart-agent="verifier"]').first().click();
  assert.equal(await page.locator('#agent-title').innerText(), 'verifier');
  await page.locator('[data-role-back]').click();
  assert.equal(await page.evaluate(()=>document.activeElement.dataset.chartAgent), 'verifier');
}));

test('appearance defaults to FWD, offers only Default and FWD, and preserves page state', () => withPage(async page => {
  assert.equal(await page.locator('html').getAttribute('data-theme'), 'fwd');
  await page.locator('.appearance-menu summary').click();
  assert.deepEqual(await page.locator('#appearance-theme option').evaluateAll(nodes=>nodes.map(n=>n.value)), ['fwd','default']);
  await page.locator('#appearance-mode').selectOption('dark');
  assert.ok(await page.locator('html').evaluate(n=>n.classList.contains('dark')&&n.classList.contains('theme-dark')));
  await page.locator('#appearance-mode').press('Escape');
  await page.locator('.nav [data-nav="skills"]').click();
  await page.getByRole('searchbox').pressSequentially('code');
  const original = await page.getByRole('searchbox').elementHandle();
  await page.locator('.appearance-menu summary').click();
  await page.locator('#appearance-theme').selectOption('default');
  assert.equal(await page.locator('html').getAttribute('data-theme'), null);
  assert.ok(await original.evaluate(n=>n.isConnected));
  assert.equal(await page.getByRole('searchbox').inputValue(), 'code');
  await page.locator('#appearance-mode').selectOption('light');
  assert.ok(await page.locator('html').evaluate(n=>n.classList.contains('theme-light')&&!n.classList.contains('dark')));
  await page.locator('#appearance-mode').selectOption('system');
  await page.emulateMedia({colorScheme:'dark'});
  await page.waitForFunction(()=>document.documentElement.classList.contains('dark'));
  await page.emulateMedia({colorScheme:'light'});
  await page.waitForFunction(()=>document.documentElement.classList.contains('light'));
  await page.locator('#appearance-theme').selectOption('fwd');
  await page.locator('#appearance-theme').press('Escape');
  assert.equal(await page.locator('.appearance-menu').getAttribute('open'), null);
  assert.ok(await page.locator('.appearance-menu summary').evaluate(n=>n===document.activeElement));
}));
