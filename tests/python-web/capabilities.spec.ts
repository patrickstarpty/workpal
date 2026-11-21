import {test, expect} from '@playwright/test';
import {mkdir} from 'node:fs/promises';

// The configured launcher creates a dedicated database and never calls a model.
test('login, capability home and workspace are three distinct layers', async ({page}) => {
  test.setTimeout(90000);
  const errors: string[] = [];
  const requests: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => {if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(request.method())) requests.push(new URL(request.url()).pathname);});
  await page.setViewportSize({width: 1440, height: 1000});
  await page.goto('/');
  await expect(page.getByRole('button', {name: 'Sign in', exact: true})).toBeVisible();
  await expect(page.getByRole('navigation', {name: 'Capabilities'})).toHaveCount(0);
  await expect(page.getByLabel('Email', {exact: true})).toHaveValue('dev@workpal.local');
  await page.getByRole('button', {name: 'Sign in', exact: true}).click();
  await expect(page).toHaveURL(/#\/home$/);
  await expect(page.getByRole('heading', {name: 'One goal. A complete lifecycle.'})).toBeVisible();
  await expect(page.getByRole('combobox', {name: 'Workspace', exact: true})).toHaveCount(0);
  await expect(page.getByRole('button', {name: 'Appearance', exact: true})).toHaveCount(0);
  await expect(page.getByRole('button', {name: 'Enter Workspace', exact: true})).toBeVisible();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'fwd');
  expect(await page.locator('.delivery-loop svg, .delivery-loop marker').count()).toBe(0);
  await mkdir('outputs/capability-frontend', {recursive: true});
  await page.screenshot({path: 'outputs/capability-frontend/overview-fwd-light.png', fullPage: true});
  await page.getByRole('button', {name: 'Explore squads', exact: true}).click();
  await expect(page.locator('#capability-content')).toBeFocused();
  expect((await page.getByRole('heading', {name: 'Your team, at a glance'}).boundingBox())!.y).toBeLessThan(300);
  await page.getByRole('navigation', {name: 'Capabilities'}).getByRole('button', {name: 'Overview', exact: true}).click();

  // A stage points to the same source-linked skill in the Hub.
  await page.getByRole('button', {name: /^Build: Code;/}).click();
  await expect(page.locator('#stage-detail-title')).toBeFocused();
  await page.getByRole('button', {name: 'test-driven-development', exact: true}).click();
  await expect(page).toHaveURL(/#\/home\/skills$/);
  await expect(page.getByRole('region', {name: 'Skill details'}).getByRole('heading')).toHaveText('test-driven-development');
  await expect(page.getByRole('region', {name: 'Skill details'}).getByRole('heading')).toBeFocused();
  await page.getByRole('button', {name: 'Back to skills', exact: true}).click();
  await page.screenshot({path: 'outputs/capability-frontend/skill-hub-fwd-light.png', fullPage: true});
  const search = page.getByRole('searchbox', {name: 'Search skills'});
  const original = await search.elementHandle();
  await search.pressSequentially('code');
  await expect(search).toHaveValue('code');
  await search.press('ArrowLeft'); await search.press('ArrowLeft');
  await search.pressSequentially('X');
  await expect(search).toHaveValue('coXde');
  expect(await search.evaluate(node => (node as HTMLInputElement).selectionStart)).toBe(3);
  expect(await original!.evaluate(node => node.isConnected)).toBe(true);
  await search.fill('');
  const beforeComposition = await page.getByRole('status').textContent();
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Input.imeSetComposition', {text: '测', selectionStart: 1, selectionEnd: 1});
  await expect(page.getByRole('status')).toHaveText(beforeComposition!);
  await cdp.send('Input.insertText', {text: '测试'});
  await expect(search).toHaveValue('测试');
  await expect(page.getByRole('status')).toHaveText('0 of 203 entries');
  await search.fill('');
  await page.getByRole('button', {name: 'Show more', exact: true}).click();
  await page.setViewportSize({width: 390, height: 844});
  const card = page.locator('[data-skill]').last();
  const id = await card.getAttribute('data-skill');
  await card.click();
  const detail = page.getByRole('region', {name: 'Skill details'}).getByRole('heading');
  await expect(detail).toBeFocused();
  await card.click();
  await expect(detail).toBeFocused();
  const box = (await detail.boundingBox())!;
  expect(box.y).toBeGreaterThanOrEqual(0); expect(box.y + box.height).toBeLessThanOrEqual(844);
  await page.getByRole('button', {name: 'Back to skills', exact: true}).click();
  expect(await page.evaluate(() => document.activeElement?.getAttribute('data-skill'))).toBe(id);
  await page.getByRole('button', {name: /^Browse Testing & review,/}).click();
  await expect(page.getByLabel('Skill type')).toHaveValue('quality');
  await expect(page.getByLabel('Skill type')).toBeFocused();

  await page.getByRole('navigation', {name: 'Capabilities'}).getByRole('button', {name: 'Agent Team'}).click();
  await page.getByRole('button', {name: 'Explore Engineering delivery squad', exact: true}).click();
  await expect(page.locator('#squad-title')).toBeFocused();
  await page.locator('[data-agent="simplifier"]').click();
  await expect(page.locator('#agent-title')).toHaveText('code simplifier');
  await expect(page.locator('#agent-title')).toBeFocused();
  await page.locator('[data-role-back]').click();
  await page.locator('[data-squad-back]').click();
  await expect(page.getByRole('button', {name: 'Explore Engineering delivery squad', exact: true})).toBeFocused();

  // Appearance is managed inside Workspace and carries back to capabilities.
  await page.getByRole('button', {name: 'Enter Workspace', exact: true}).click();
  await expect(page.getByRole('heading', {name: 'Choose a workspace'})).toBeVisible();
  const slug = 'landing'; // This permitted workspace name must not collide with capability routes.
  await page.getByLabel('Name', {exact: true}).fill('Capability acceptance');
  await page.getByLabel('Workspace URL').fill(slug);
  await page.getByRole('button', {name: 'Create workspace', exact: true}).click();
  await expect(page).toHaveURL(new RegExp(`#/${slug}/projects$`));
  await expect(page.getByRole('combobox', {name: 'Workspace', exact: true})).toHaveValue(slug);
  const setWorkspaceAppearance = async (theme: string, mode: string) => {
    await page.getByRole('button', {name: 'Account', exact: true}).click();
    await page.getByRole('menuitem', {name: /^Theme/}).click();
    await expect(page.getByRole('menuitemradio')).toHaveText(['Light', 'Dark', 'System', 'FWD', 'Default']);
    const selection = page.getByRole('menuitemradio', {name: theme === 'fwd' ? 'FWD' : 'Default', exact: true});
    await selection.click();
    await expect(selection).toHaveAttribute('aria-checked', 'true');
    await page.getByRole('menuitemradio', {name: mode === 'light' ? 'Light' : 'Dark', exact: true}).click();
    await expect(page.getByRole('menuitemradio')).toHaveCount(0);
  };
  const enterCreatedWorkspace = async () => {
    await page.getByRole('button', {name: 'Enter Workspace', exact: true}).click();
    const chooser = page.getByRole('heading', {name: 'Choose a workspace'});
    await expect(chooser.or(page.getByRole('combobox', {name: 'Workspace', exact: true}))).toBeVisible();
    if (await chooser.isVisible()) await page.getByRole('button', {name: 'Capability acceptance', exact: true}).click();
    await expect(page.getByRole('combobox', {name: 'Workspace', exact: true})).toHaveValue(slug);
  };
  await page.getByRole('link', {name: 'AI capabilities', exact: true}).click();
  for (const theme of ['fwd', 'default']) for (const mode of ['light', 'dark']) {
    await page.setViewportSize({width: 1440, height: 900});
    await enterCreatedWorkspace();
    await setWorkspaceAppearance(theme, mode);
    await page.getByRole('link', {name: 'AI capabilities', exact: true}).click();
    await expect(page.getByRole('button', {name: 'Appearance', exact: true})).toHaveCount(0);
    if (theme === 'fwd') await expect(page.locator('html')).toHaveAttribute('data-theme', 'fwd');
    else await expect(page.locator('html')).not.toHaveAttribute('data-theme');
    await expect(page.locator('html')).toHaveClass(new RegExp(`\\b${mode}\\b`));
    const contrast = () => page.getByRole('button', {name: 'Enter Workspace', exact: true}).evaluate(node => {
      const style = getComputedStyle(node); const canvas = document.createElement('canvas'); canvas.width = canvas.height = 1;
      const ctx = canvas.getContext('2d')!;
      const luminance = (color: string) => {ctx.fillStyle = color; ctx.fillRect(0, 0, 1, 1); return [...ctx.getImageData(0, 0, 1, 1).data].slice(0, 3).map(v => {const x = v / 255; return x <= 0.04045 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4;}).reduce((sum, v, i) => sum + v * [0.2126, 0.7152, 0.0722][i]!, 0);};
      const a = luminance(style.color), b = luminance(style.backgroundColor); return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    });
    await expect.poll(contrast, {message: `${theme}/${mode} workspace button contrast`}).toBeGreaterThanOrEqual(4.5);
    for (const width of [320, 390, 728, 1440]) {
      await page.setViewportSize({width, height: 900});
      for (const view of ['Overview', 'Skill Hub', 'Agent Team']) {
        await page.evaluate(() => window.scrollTo({top: 0, behavior: 'instant'}));
        await page.getByRole('navigation', {name: 'Capabilities'}).getByRole('button', {name: view, exact: true}).click();
        await expect.poll(() => page.evaluate(() => window.scrollY), {message: `${theme}/${mode}/${width}/${view} keeps the header in view`}).toBe(0);
        await expect(page.getByRole('button', {name: 'Enter Workspace', exact: true})).toBeInViewport();
        await expect(page.getByRole('button', {name: 'Appearance', exact: true})).toHaveCount(0);
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${theme}/${mode}/${width}/${view}`).toBe(true);
      }
    }
  }
  await page.screenshot({path: 'outputs/capability-frontend/team-default-dark.png', fullPage: true});
  await page.setViewportSize({width: 390, height: 844});
  await page.screenshot({path: 'outputs/capability-frontend/team-mobile-dark.png', fullPage: true});
  await page.setViewportSize({width: 1440, height: 900});
  await enterCreatedWorkspace();
  await expect(page).toHaveURL(new RegExp(`#/${slug}/projects$`));
  await setWorkspaceAppearance('fwd', 'dark');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'fwd');
  await page.setViewportSize({width: 390, height: 844});
  expect(await page.locator('[data-app-shell]').evaluate(node => node.getBoundingClientRect().bottom <= innerHeight + 1)).toBe(true);
  await page.goto('/#/landing/skills');
  await expect(page.getByRole('combobox', {name: 'Workspace', exact: true})).toHaveValue(slug);
  await expect(page.getByRole('navigation', {name: 'Capabilities'})).toHaveCount(0);
  await expect(page.locator('html')).toHaveClass(/dark/);
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'fwd');
  await page.getByRole('link', {name: 'AI capabilities', exact: true}).click();
  await expect(page).toHaveURL(/#\/home$/);
  await page.reload();
  await expect(page.getByRole('button', {name: 'Enter Workspace', exact: true})).toBeVisible();
  await expect(page.getByRole('combobox', {name: 'Workspace', exact: true})).toHaveCount(0);
  await page.getByRole('button', {name: 'Enter Workspace', exact: true}).click();
  const chooser = page.getByRole('heading', {name: 'Choose a workspace'});
  await expect(chooser.or(page.getByRole('combobox', {name: 'Workspace', exact: true}))).toBeVisible();
  if (await chooser.isVisible()) await page.getByRole('button', {name: 'Capability acceptance', exact: true}).click();
  await expect(page).toHaveURL(new RegExp(`#/${slug}/projects$`));
  await page.goto(`/#/${slug}/issues`); await page.reload();
  await expect(page.getByRole('combobox', {name: 'Workspace', exact: true})).toHaveValue(slug);
  await expect(page).toHaveURL(new RegExp(`#/${slug}/issues$`));
  expect(errors).toEqual([]);
  expect(requests.filter(path => /^\/(api|v1)\/.*\/(run|install|send)(\/|$)/.test(path))).toEqual([]);
});
