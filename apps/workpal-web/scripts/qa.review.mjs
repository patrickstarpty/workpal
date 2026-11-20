import assert from 'node:assert/strict';
import {withBrowser, signIn} from './browser-fixture.mjs';

await withBrowser(async ({base, newPage, runPython, expect}) => {
  const failures = [];
  async function test(name, run) {
    const pages = [];
    const open = async () => { const page = await newPage(); pages.push(page); return page; };
    try { await run(open); console.log('PASS ' + name); }
    catch (error) { failures.push(name); console.error('FAIL ' + name + '\n' + error.message); }
    finally { for (const page of pages) await page.context().close(); }
  }
  async function workspace(page) {
    await signIn(page, base);
    await page.getByLabel('Workspace', {exact:true}).selectOption('1');
    await page.getByRole('button', {name:'Edit workspace'}).waitFor();
  }
  async function rename(page, name) {
    await page.getByRole('button', {name:'Edit workspace'}).click();
    await page.getByLabel('Workspace name').fill(name);
    await page.getByRole('button', {name:'Save', exact:true}).click();
    await page.getByRole('heading', {name, exact:true}).waitFor();
  }
  await test('invalid credentials preserve the usable login form', async open => {
    const page = await open(); await signIn(page, base, 'owner', 'wrong-password');
    await expect(page.getByRole('alert')).toContainText('Invalid credentials');
    await expect(page.getByLabel('Username')).toHaveValue('owner');
    await expect(page.getByLabel('Password')).toHaveValue('');
    await page.getByLabel('Password').fill('qa-password');
    await page.getByRole('button', {name:'Sign in', exact:true}).click();
    await expect(page.getByLabel('Workspace', {exact:true})).toBeVisible();
  });
  await test('real concurrent rename preserves a draft through conflict and reload', async open => {
    const first = await open(), second = await open(); await workspace(first); await workspace(second);
    await first.getByRole('button', {name:'Edit workspace'}).click();
    await first.getByLabel('Workspace name').fill('My preserved draft');
    await rename(second, 'Concurrent change');
    await first.getByRole('button', {name:'Save', exact:true}).click();
    await expect(first.getByRole('alert')).toContainText('workspace changed');
    await expect(first.getByLabel('Workspace name')).toHaveValue('My preserved draft');
    await first.getByRole('button', {name:'Reload workspace'}).click();
    await expect(first.getByRole('heading', {name:'Concurrent change', exact:true})).toBeVisible();
    await expect(first.getByLabel('Workspace name')).toHaveValue('My preserved draft');
    await first.getByRole('button', {name:'Save', exact:true}).click();
    await expect(first.getByRole('heading', {name:'My preserved draft', exact:true})).toBeVisible();
  });
  await test('saved workspace name also updates the selected workspace label', async open => {
    const page = await open(); await workspace(page); await rename(page, 'All labels agree');
    await expect(page.locator('select option:checked')).toContainText('All labels agree');
  });
  await test('known validation failure remains editable and is not an unknown save', async open => {
    const page = await open(); await workspace(page);
    await page.getByRole('button', {name:'Edit workspace'}).click();
    await page.getByLabel('Workspace name').fill('   ');
    const response = page.waitForResponse(r => r.url().endsWith('/actions/workspace.rename'));
    await page.getByRole('button', {name:'Save', exact:true}).click();
    assert.equal((await response).status(), 400);
    await expect(page.getByLabel('Workspace name')).toBeEnabled();
    await expect(page.getByRole('alert')).not.toContainText('not been confirmed');
    await page.getByLabel('Workspace name').fill('Valid correction');
    await page.getByRole('button', {name:'Save', exact:true}).click();
    await expect(page.getByRole('heading', {name:'Valid correction', exact:true})).toBeVisible();
  });
  await test('committed response loss retries the exact intent once', async open => {
    const page = await open(); await workspace(page);
    const requests = []; let saved;
    await page.route('**/api/v1/actions/workspace.rename', async route => {
      requests.push(route.request().postDataJSON());
      if (requests.length === 1) { const response = await route.fetch(); assert.equal(response.status(), 200); saved = await response.json(); await route.abort('failed'); }
      else await route.continue();
    });
    await page.getByRole('button', {name:'Edit workspace'}).click();
    await page.getByLabel('Workspace name').fill('Confirmed after response loss');
    await page.getByRole('button', {name:'Save', exact:true}).click();
    await expect(page.getByRole('alert')).toContainText('not been confirmed');
    await expect(page.getByLabel('Workspace name')).toBeDisabled();
    await page.getByRole('button', {name:'Retry save', exact:true}).click();
    await expect(page.getByRole('heading', {name:'Confirmed after response loss', exact:true})).toBeVisible();
    assert.equal(requests.length, 2); assert.deepEqual(requests[0], requests[1]);
    runPython(`from workpal.identity.models import Workspace; from workpal.audit.models import AuditEvent, Outbox; from workpal.actions.models import IdempotencyResult; assert Workspace.objects.get(pk=1).revision == ${saved.data.revision}; assert IdempotencyResult.objects.filter(key='${requests[0].idempotency_key}').count() == 1; assert AuditEvent.objects.filter(action_id='workspace.rename',fields__name='Confirmed after response loss').count() == 1; assert Outbox.objects.filter(action_id='workspace.rename',event__fields__name='Confirmed after response loss').count() == 1`);
  });
  await test('actual membership revocation clears the old page and edit dialog', async open => {
    runPython("from django.contrib.auth import get_user_model; from workpal.identity.models import Membership, Workspace; u=get_user_model().objects.create_user(username='temporary-admin',password='qa-password'); Membership.objects.create(user=u,workspace_id=1,role='admin')");
    const page = await open(); await signIn(page, base, 'temporary-admin');
    await page.getByLabel('Workspace', {exact:true}).selectOption('1');
    await page.getByRole('button', {name:'Edit workspace'}).click();
    await page.getByLabel('Workspace name').fill('Must never be saved');
    runPython("from workpal.identity.service import manage_members; from workpal.contracts import Actor; from workpal.identity.models import Membership; m=Membership.objects.get(user__username='temporary-admin'); manage_members(Actor(1,1),1,dict(role=None,revision=m.revision),m.pk,revoke=True)");
    await page.getByRole('button', {name:'Save', exact:true}).click();
    await expect(page.getByRole('button', {name:'Refresh account'})).toBeVisible();
    await expect(page.locator('dialog')).toHaveCount(0);
    await expect(page.getByRole('heading', {name:'Confirmed after response loss', exact:true})).toHaveCount(0);
    await page.getByRole('button', {name:'Refresh account'}).click();
    await expect(page.getByText('No workspaces are available.')).toBeVisible();
    await expect(page.getByRole('button', {name:'Sign out'})).toBeVisible();
  });
  await test('late workspace read cannot replace a different selected workspace', async open => {
    const page = await open(); await signIn(page, base);
    let release, arrived;
    const held = new Promise(resolve => { release = resolve; });
    const waiting = new Promise(resolve => { arrived = resolve; });
    await page.route('**/api/v1/actions/workspace.read', async route => {
      if (route.request().postDataJSON().workspace_id === 1) {
        const response = await route.fetch(); arrived(); await held; await route.fulfill({response});
      } else await route.continue();
    });
    try {
      await page.getByLabel('Workspace', {exact:true}).selectOption('1'); await waiting;
      await page.getByLabel('Workspace', {exact:true}).selectOption('2');
      await expect(page.getByRole('heading', {name:'Second', exact:true})).toBeVisible();
      const settled = page.waitForResponse(r => r.url().endsWith('/actions/workspace.read') && r.request().postDataJSON().workspace_id === 1);
      release(); await settled;
      await expect(page.getByRole('heading', {name:'Second', exact:true})).toBeVisible();
      await expect(page.getByLabel('Workspace', {exact:true})).toHaveValue('2');
    } finally { release(); }
  });
  await test('lost logout response clears facts and reports the unconfirmed outcome', async open => {
    const page = await open(); await workspace(page);
    await page.route('**/api/v1/auth/logout', async route => {
      const response = await route.fetch(); assert.equal(response.status(), 200); await route.abort('failed');
    });
    await page.getByRole('button', {name:'Sign out'}).click();
    await expect(page.getByRole('alert')).toHaveText('Sign out has not been confirmed.');
    await expect(page.getByRole('button', {name:'Edit workspace'})).toHaveCount(0);
    await expect(page.getByLabel('Workspace', {exact:true})).toHaveCount(0);
    await page.getByRole('button', {name:'Refresh account'}).click();
    await expect(page.getByLabel('Username')).toBeVisible();
  });
  await test('long account names fit the narrow layout', async open => {
    runPython("from django.contrib.auth import get_user_model; from workpal.identity.models import Membership; u=get_user_model().objects.create_user(username='u'*150,password='qa-password'); Membership.objects.create(user=u,workspace_id=1,role='member')");
    const page = await open(); await page.setViewportSize({width:390,height:844});
    await signIn(page, base, 'u'.repeat(150));
    await page.getByLabel('Workspace', {exact:true}).selectOption('1');
    await expect(page.getByRole('heading', {name:'Confirmed after response loss', exact:true})).toBeVisible();
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'no horizontal overflow for a valid long username');
  });
  assert.deepEqual(failures, [], 'browser review failures');
});
