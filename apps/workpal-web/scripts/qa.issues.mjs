import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {withBrowser, signIn} from './browser-fixture.mjs';
await withBrowser(async ({base, newPage, expect, runPython, repo}) => {
  runPython(`from workpal.contracts import Actor
from workpal.work import issues, service
actor=Actor(1,1)
p=service.create(actor,name='Real project')
i=issues.create(actor,p['id'],'Old title',description='Old description',criteria=[{'key':'old','text':'Old criterion'}])
issues.update(actor,i['id'],1,title='Current <img src=x>',description='Current description',criteria=[{'key':'new','text':'Current criterion'}])
for n in range(22): issues.create(actor,p['id'],'Extra '+str(n))`);
  const snapshot = () => runPython("from workpal.work.models import Issue, IssueRequirements; import json; print(json.dumps([list(Issue.objects.values()),list(IssueRequirements.objects.values())],default=str,sort_keys=True))");
  const before = snapshot();
  const page = await newPage();
  await signIn(page, base);
  await page.getByLabel('Workspace', {exact:true}).selectOption('1');
  await page.getByRole('button', {name:'Issues', exact:true}).click();
  await page.getByRole('button', {name:'Load more', exact:true}).click();
  await expect(page.locator('.project-row')).toHaveCount(23);
  await page.getByLabel('Search issues').fill('Current');
  await expect(page.locator('.project-row')).toHaveCount(1);
  const choice = page.getByRole('button', {name:'Current <img src=x> (#1)', exact:true});
  await choice.focus(); await page.keyboard.press('Enter');
  await expect(page.getByRole('heading', {name:'Requirements version 2', exact:true})).toBeVisible();
  await page.getByRole('button', {name:'Previous version'}).click();
  await expect(page.getByRole('heading', {name:'Requirements version 1', exact:true})).toBeVisible();
  await expect(page.getByRole('heading', {name:'Old title', exact:true})).toBeVisible();
  await page.getByRole('button', {name:'Next version'}).click();
  await expect(page.getByRole('heading', {name:'Requirements version 2', exact:true})).toBeVisible();
  assert.equal(await page.locator('main img').count(), 0);
  await mkdir(repo+'/outputs/workpal-web', {recursive:true});
  for (const [name,width] of [['desktop',1440],['mobile',390]]) {
    await page.setViewportSize({width,height:900});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.screenshot({path:repo+'/outputs/workpal-web/a54a-issues-'+name+'.png'});
  }
  await page.context().setOffline(true);
  await page.getByRole('button', {name:'Refresh issues'}).click();
  await expect(page.getByRole('alert')).toContainText('unknown');
  await expect(page.getByText('No issues found.', {exact:true})).toHaveCount(0);
  await page.context().setOffline(false);
  await page.getByRole('button', {name:'Retry', exact:true}).click();
  await expect(page.locator('.project-row')).toHaveCount(1);
  const reader = await newPage();
  await signIn(reader, base, 'reader');
  await reader.getByLabel('Workspace', {exact:true}).selectOption('1');
  await reader.getByRole('button', {name:'Issues', exact:true}).click();
  await reader.getByLabel('Search issues').fill('Current');
  await reader.getByRole('button', {name:'Current <img src=x> (#1)', exact:true}).click();
  await expect(reader.getByRole('heading', {name:'Requirements version 2', exact:true})).toBeVisible();
  await reader.context().close();
  await page.getByLabel('Workspace', {exact:true}).selectOption('2');
  await page.getByRole('button', {name:'Issues', exact:true}).click();
  await expect(page.getByText('No issues found.', {exact:true})).toBeVisible();
  await expect(page.getByText('Current description', {exact:true})).toHaveCount(0);
  assert.equal(snapshot(), before);
  console.log('issues: real list, pagination, search, keyboard, current/history, unchanged entities and 1440/390 passed');
});
