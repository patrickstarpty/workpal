import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {withBrowser, signIn} from './browser-fixture.mjs';

await withBrowser(async ({base, newPage, expect, runPython, repo}) => {
  runPython(`from workpal.contracts import Actor
from workpal.work import service
service.create(Actor(1,1), name='Creation project')`);
  const page = await newPage();
  await signIn(page, base, 'reader');
  await page.getByLabel('Workspace', {exact:true}).selectOption('1');
  await page.getByRole('button', {name:'Issues', exact:true}).click();
  await expect(page.getByText('No issues found.', {exact:true})).toBeVisible();
  const opener = page.getByRole('button', {name:'Create issue', exact:true});
  await opener.click({timeout:5000});
  const dialog = page.getByRole('dialog', {name:'Create issue', exact:true});
  await expect(dialog).toBeVisible();
  await dialog.getByRole('button', {name:'Creation project (#1)', exact:true}).click();
  await dialog.getByRole('button', {name:'owner (#1)', exact:true}).click();
  await dialog.getByLabel('Title', {exact:true}).fill('Created <img src=x>');
  await dialog.getByLabel('Description', {exact:true}).fill('Details entered through the form.');
  for (const [number, text] of [[1, 'Keep first'], [2, 'Remove middle'], [3, 'Keep third']]) {
    await dialog.getByRole('button', {name:'Add criterion', exact:true}).click();
    await dialog.getByLabel(`Acceptance criterion ${number}`, {exact:true}).fill(text);
  }
  await dialog.getByRole('button', {name:'Remove criterion 2', exact:true}).click();
  await expect(dialog.getByLabel('Acceptance criterion 1', {exact:true})).toHaveValue('Keep first');
  await expect(dialog.getByLabel('Acceptance criterion 3', {exact:true})).toHaveValue('Keep third');
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  await expect(opener).toBeFocused();
  await opener.click();
  await expect(dialog.getByLabel('Title', {exact:true})).toHaveValue('Created <img src=x>');
  await mkdir(repo + '/outputs/workpal-web', {recursive:true});
  for (const [name, width] of [['desktop', 1440], ['mobile', 390]]) {
    await page.setViewportSize({width, height:1000});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    const bounds = await dialog.boundingBox();
    assert(bounds && bounds.x >= 0 && bounds.x + bounds.width <= width);
    await page.screenshot({path:repo + `/outputs/workpal-web/a54b2-create-${name}.png`});
  }
  await dialog.getByRole('button', {name:'Create issue', exact:true}).click();
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole('heading', {name:'Requirements version 1', exact:true})).toBeVisible();
  await expect(page.locator('.issue-detail')).toContainText('Created <img src=x>');
  assert.equal(await page.locator('main img').count(), 0);
  runPython(`from workpal.work.models import Issue, IssueRequirements
from workpal.actions.models import IdempotencyResult
from workpal.audit.models import AuditEvent, Outbox
i=Issue.objects.get()
r=i.current_requirements
assert (i.project_id,i.created_by_id,i.assignee_id,i.status_key)==(1,2,1,'backlog')
assert r.title=='Created <img src=x>' and r.description=='Details entered through the form.'
assert r.criteria==[{'key':'criterion_1','text':'Keep first'},{'key':'criterion_3','text':'Keep third'}]
assert r.number==1 and IssueRequirements.objects.count()==1
assert IdempotencyResult.objects.filter(action_id='issue.create').count()==1
assert AuditEvent.objects.filter(action_id='issue.create').count()==1
assert Outbox.objects.filter(action_id='issue.create').count()==1`);
  const fresh = await newPage();
  await signIn(fresh, base, 'reader');
  await fresh.getByLabel('Workspace', {exact:true}).selectOption('1');
  await fresh.getByRole('button', {name:'Issues', exact:true}).click();
  await fresh.getByRole('button', {name:'Created <img src=x> (#1)', exact:true}).click();
  await expect(fresh.getByRole('heading', {name:'Requirements version 1', exact:true})).toBeVisible();
  await expect(fresh.locator('.issue-detail')).toContainText('Keep third');
  await fresh.getByRole('button', {name:'Create issue', exact:true}).click();
  const empty = fresh.getByRole('dialog', {name:'Create issue', exact:true});
  await empty.getByRole('button', {name:'Creation project (#1)', exact:true}).click();
  await empty.getByLabel('Title', {exact:true}).fill('Unassigned issue');
  await empty.getByRole('button', {name:'Create issue', exact:true}).click();
  await expect(empty).toHaveCount(0);
  await expect(fresh.locator('.issue-detail')).toContainText('Unassigned issue');
  runPython(`from workpal.work.models import Issue, IssueRequirements
i=Issue.objects.get(current_requirements__title='Unassigned issue')
assert i.assignee_id is None and i.current_requirements.criteria==[]
assert Issue.objects.count()==2 and IssueRequirements.objects.count()==2`);
  console.log('issue creation core: member, real selectors, criteria edits, Escape draft, persistence, unassigned and 1440/390 passed');
});
