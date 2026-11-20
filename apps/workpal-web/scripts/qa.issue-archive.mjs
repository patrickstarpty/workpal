import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {withBrowser, signIn} from './browser-fixture.mjs';
await withBrowser(async ({base, newPage, expect, runPython, repo}) => {
  runPython(`from workpal.contracts import Actor
from workpal.work import issues, service, transitions
actor=Actor(1,1)
p=service.create(actor,name='Real project')
i=issues.create(actor,p['id'],'Old title',description='Old description',criteria=[{'key':'old','text':'Old criterion'}])
issues.update(actor,i['id'],1,title='Current <img src=x>XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX',description='Current description',criteria=[{'key':'new','text':'Current criterion'}])
transitions.transition(actor,i['id'],next(s['key'] for s in i['workflow_snapshot']['definition']['states'] if s['category']=='todo'),2)\nissues.create(actor,p['id'],'Child',parent_issue_id=i['id'])\nfor n in range(22): issues.create(actor,p['id'],'Extra '+str(n))`);
  const coreFacts = () => JSON.parse(runPython(`import json
from workpal.work.models import Issue,IssueRequirements
from workpal.collaboration.models import Notification
print(json.dumps(dict(issues=list(Issue.objects.order_by('pk').values()),versions=list(IssueRequirements.objects.order_by('pk').values()),notifications=list(Notification.objects.order_by('pk').values())),default=str))`).trim().split('\n').at(-1));
  const coreBefore=coreFacts();
  const page = await newPage();
  await signIn(page, base, 'reader');
  await page.getByLabel('Workspace', {exact:true}).selectOption('1');
  await page.getByRole('button', {name:'Issues', exact:true}).click();
  await page.getByLabel('Search issues').fill('Current');
  await page.getByRole('button', {name:'Current <img src=x>XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX (#1)', exact:true}).click();
  await expect(page.getByRole('heading', {name:'Requirements version 2', exact:true})).toBeVisible();
  const archive = page.getByRole('button', {name:'Archive issue', exact:true});
  await archive.click({timeout:2000});
  await page.keyboard.press('Escape');
  await expect(archive).toBeFocused();
  await archive.click();
  await page.getByRole('dialog').getByRole('button', {name:'Cancel', exact:true}).click();
  await archive.click();
  await page.getByRole('dialog').getByRole('button', {name:'Archive issue', exact:true}).click();
  await expect(page.locator('.project-row')).toHaveCount(0);
  await page.getByLabel('Include archived').check();
  await page.getByRole('button', {name:'Current <img src=x>XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX (#1)', exact:true}).click();
  await expect(page.getByRole('button', {name:'Restore issue', exact:true})).toBeVisible();
  await page.getByRole('button', {name:'Previous version'}).click();
  await expect(page.getByRole('heading', {name:'Requirements version 1', exact:true})).toBeVisible();
  await mkdir(repo+'/outputs/workpal-web', {recursive:true});
  for (const [name,width] of [['desktop',1440],['mobile',390]]) {
    await page.setViewportSize({width,height:900});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.screenshot({path:repo+'/outputs/workpal-web/a54b4-archive-'+name+'.png'});
  }
  const fresh = await newPage();
  await signIn(fresh,base,'reader');
  await fresh.getByLabel('Workspace',{exact:true}).selectOption('1');
  await fresh.getByRole('button',{name:'Issues',exact:true}).click();
  await fresh.getByLabel('Include archived').check();
  await fresh.getByLabel('Search issues').fill('Current');
  await fresh.locator('.project-row button').click();
  await expect(fresh.getByRole('button',{name:'Restore issue',exact:true})).toBeVisible();
  assert.equal(await fresh.locator('main img').count(),0);
  await fresh.context().close();
  await page.getByRole('button', {name:'Restore issue', exact:true}).click();
  await page.getByRole('dialog').getByRole('button', {name:'Restore issue', exact:true}).click();
  await expect(page.getByRole('button', {name:'Archive issue', exact:true})).toBeVisible();
  const counts=JSON.parse(runPython(`import json
from workpal.audit.models import AuditEvent,Outbox
from workpal.actions.models import IdempotencyResult
print(json.dumps([[AuditEvent.objects.filter(action_id=a,fields__issue_id=1).count(),Outbox.objects.filter(action_id=a,event__fields__issue_id=1).count(),IdempotencyResult.objects.filter(action_id=a,result__data__id=1).count()] for a in ['issue.archive','issue.restore']]))`).trim().split('\n').at(-1));
  assert.deepEqual(counts,[[1,1,1],[1,1,1]]);
  const coreAfter=coreFacts();
  assert.deepEqual(coreAfter.versions,coreBefore.versions);
  assert.deepEqual(coreAfter.notifications,coreBefore.notifications);
  assert.deepEqual(coreAfter.issues.slice(1),coreBefore.issues.slice(1));
  assert.equal(coreAfter.issues[0].revision,coreBefore.issues[0].revision+2);
  for(const key of Object.keys(coreBefore.issues[0]))if(!['revision','updated_at'].includes(key))assert.deepEqual(coreAfter.issues[0][key],coreBefore.issues[0][key]);
  console.log('core SQL before/after',JSON.stringify({before:coreBefore,after:coreAfter}));
  console.log('member archive, history, restore, keyboard and responsive screenshots passed');
  const parse = code => JSON.parse(runPython(code).trim().split('\n').at(-1));
  const seed = parse(`import json
from workpal.contracts import Actor
from workpal.work import issues,service
a=Actor(1,1);p=service.create(a,'Archive races')
print(json.dumps([issues.create(a,p['id'],'Race '+str(n)) for n in range(4)]))`);
  const state = id => parse(`import json
from workpal.work.models import Issue,IssueRequirements
from workpal.actions.models import IdempotencyResult
from workpal.audit.models import AuditEvent,Outbox
print(json.dumps(dict(issue=Issue.objects.values().get(pk=${id}),versions=list(IssueRequirements.objects.filter(issue_id=${id}).values()),audit=AuditEvent.objects.filter(action_id='issue.archive',fields__issue_id=${id}).count(),outbox=Outbox.objects.filter(action_id='issue.archive',event__fields__issue_id=${id}).count(),cache=IdempotencyResult.objects.filter(action_id='issue.archive',result__data__id=${id}).count()),default=str))`);
  async function select(item) {
    const p = await newPage();
    await signIn(p,base,'reader');
    await p.getByLabel('Workspace',{exact:true}).selectOption('1');
    await p.getByRole('button',{name:'Issues',exact:true}).click();
    await p.getByLabel('Search issues').fill(item.title);
    await p.getByRole('button',{name:`${item.title} (#${item.id})`,exact:true}).click();
    await expect(p.getByRole('heading',{name:'Requirements version 1',exact:true})).toBeVisible();
    return p;
  }
  async function dialog(p) {await p.getByRole('button',{name:'Archive issue',exact:true}).click();return p.getByRole('dialog');}
  for (const edited of [false,true]) {
    const item=seed[edited?1:0], a=await select(item),b=await select(item),db=await dialog(b);
    const requests=[];b.on('request',r=>{if(r.url().endsWith('/actions/issue.archive'))requests.push(r.postDataJSON());});
    if (edited) {
      await a.getByRole('button',{name:'Edit requirements',exact:true}).click();
      await a.getByRole('dialog').getByLabel('Title',{exact:true}).fill('Changed race title');
      await a.getByRole('dialog').getByRole('button',{name:'Save changes',exact:true}).click();
      await expect(a.getByRole('dialog')).toHaveCount(0);
    } else {
      const da=await dialog(a);await da.getByRole('button',{name:'Archive issue',exact:true}).click();await expect(da).toHaveCount(0);
    }
    await db.getByRole('button',{name:'Archive issue',exact:true}).click();
    await expect(db.getByRole('button',{name:'Reload current',exact:true})).toBeVisible();
    await db.getByRole('button',{name:'Reload current',exact:true}).click();
    if (edited) {
      await expect(db).toContainText('Changed race title');await expect(db).toContainText('Active');
      await db.getByRole('button',{name:'Archive issue',exact:true}).click();
    } else {
      await expect(db).toContainText('Already archived');
      await db.getByRole('button',{name:'Refresh issue',exact:true}).click();
    }
    await expect(db).toHaveCount(0);
    assert.equal(requests.length,edited?2:1);assert.equal(requests[0].expected_revision,1);
    if(edited){assert.equal(requests[1].expected_revision,2);assert.notEqual(requests[0].idempotency_key,requests[1].idempotency_key);}
    console.log('conflict archive requests',JSON.stringify(requests));
    const fact=state(item.id);console.log('conflict SQL',JSON.stringify(fact));assert.equal(fact.issue.revision,edited?3:2);
    assert.equal(fact.versions.length,edited?2:1);
    for(const key of ['audit','outbox','cache'])assert.equal(fact[key],1);
    await a.context().close();await b.context().close();
  }
  for (const pending of [false,true]) {
    const item=seed[pending?3:2],p=await select(item),before=state(item.id),d=await dialog(p),attempts=[];
    let release,arrived;
    const gate=new Promise(r=>release=r),ready=new Promise(r=>arrived=r);
    await p.route('**/api/v1/actions/issue.archive',async route=>{
      attempts.push(route.request().postDataJSON());
      if(attempts.length!==1)return route.continue();
      const response=await route.fetch();arrived();
      if(pending){await gate;await route.fulfill({response});}else await route.abort('failed');
    });
    await d.getByRole('button',{name:'Archive issue',exact:true}).click();
    await ready;
    if(!pending)await expect(d.getByRole('button',{name:'Retry original request',exact:true})).toBeEnabled();
    await p.keyboard.press('Escape');await dialog(p);
    await expect(d.getByRole('button',{name:'Retry original request',exact:true})).toBeEnabled();
    if(pending){release();await p.waitForLoadState('networkidle');await expect(d).toBeVisible();}
    await d.getByRole('button',{name:'Retry original request',exact:true}).click();
    await expect(d).toHaveCount(0);assert.deepEqual(attempts[0],attempts[1]);assert.equal(attempts.length,2);console.log('retry requests',JSON.stringify(attempts));
    const after=state(item.id);assert.equal(after.issue.revision,before.issue.revision+1);assert.deepEqual(after.versions,before.versions);
    for(const key of ['audit','outbox','cache'])assert.equal(after[key],1);
    await p.context().close();
  }
  console.log('conflict reload, explicit new intent, lost response and in-flight reopen passed');

});
