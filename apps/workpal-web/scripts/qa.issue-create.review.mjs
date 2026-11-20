import assert from 'node:assert/strict';
import {withBrowser, signIn} from './browser-fixture.mjs';

await withBrowser(async ({base, newPage, runPython, expect}) => {
  const seed = JSON.parse(runPython(`
import json
from django.contrib.auth import get_user_model
from workpal.identity.models import Workspace, Membership
from workpal.work import service, issues
from workpal.contracts import Actor, ObjectRef
from workpal.access.service import register_object
from workpal.access.models import SourceGrant, RegisteredObject
a=Actor(1,1)
hidden=register_object(1,ObjectRef('source','create-hidden'),is_source=True)
gate=register_object(1,ObjectRef('source','create-revocable'),is_source=True)
data={}
for n in range(25):
    if n in (0,10,24):
        p=service.create(a,'Page hidden '+str(n)); register_object(1,service.ref(p['id']),[hidden])
        u=get_user_model().objects.create(username='Person inactive '+str(n),is_active=False); Membership.objects.create(user=u,workspace_id=1,role='member')
        u=get_user_model().objects.create(username='Person foreign '+str(n)); Membership.objects.create(user=u,workspace_id=2,role='member')
    service.create(a,'Page '+str(n).zfill(2))
    u=get_user_model().objects.create(username='Person '+str(n).zfill(2)); Membership.objects.create(user=u,workspace_id=1,role='member')
for key,name in [('normal','Normal'),('archive','Archive during edit'),('revocable','Source revoked'),('private','Private project'),('first','Duplicate'),('second','Duplicate')]:
    data[key]=service.create(a,name,'Description '+key)
for key in ('revocable','private'): register_object(1,service.ref(data[key]['id']),[gate])
SourceGrant.objects.create(user_id=1,source=RegisteredObject.objects.get(kind=gate.kind,object_id=gate.id),read=True,write=True)
archived=service.create(a,'Page archived'); service.update(a,archived['id'],archived['revision'],archived=True)
data['existing']=issues.create(a,data['normal']['id'],'Existing selection')
data['candidate']=get_user_model().objects.create(username='Revocable candidate').pk
Membership.objects.create(user_id=data['candidate'],workspace_id=1,role='member')
data['other']=service.create(Actor(1,2),'Other workspace')
empty=Workspace.objects.create(name='Empty'); Membership.objects.create(user_id=1,workspace=empty,role='owner'); data['empty']=empty.pk
print(json.dumps(data))`).trim().split('\n').at(-1));
  const failures = [];
  async function test(name, fn) {
    if (process.env.WORKPAL_QA_FILTER && !new RegExp(process.env.WORKPAL_QA_FILTER).test(name)) return;
    const pages = [];
    const open = async viewport => {
      const p = await newPage(viewport); p.setDefaultTimeout(6000); pages.push(p); return p;
    };
    try { await fn(open); console.log('PASS ' + name); }
    catch (error) { failures.push(name); console.error('FAIL ' + name + '\n' + error.message); }
    finally { for (const p of pages) await p.context().close(); }
  }
  async function issues(p, ws='1') {
    await signIn(p, base);
    await p.getByLabel('Workspace', {exact:true}).selectOption(ws);
    await p.getByRole('button', {name:'Issues', exact:true}).click();
    await p.getByRole('button', {name:'Create issue', exact:true}).waitFor();
  }
  async function compose(p, project=seed.normal, title='Review issue') {
    await p.getByRole('button', {name:'Create issue', exact:true}).click();
    const d = p.getByRole('dialog', {name:'Create issue', exact:true});
    if (project) {
      await d.getByLabel('Search projects').fill(project.name);
      await d.getByRole('button', {name:`${project.name} (#${project.id})`, exact:true}).click();
    }
    await d.getByLabel('Title', {exact:true}).fill(title);
    return d;
  }
  async function hold(p, action, matches=()=>true) {
    let release, arrived, used=false;
    const pending = new Set();
    const track = request => pending.add(request.url());
    const done = request => pending.delete(request.url());
    p.on('request', track); p.on('requestfinished', done); p.on('requestfailed', done);
    const released = new Promise(resolve => {release=resolve;});
    const ready = new Promise(resolve => {arrived=resolve;});
    const pattern='**/api/v1/actions/'+action;
    const handler=async route => {
      if (!used && matches(route.request().postDataJSON())) {
        used=true; const response=await route.fetch(); arrived(); await released;
        await route.fulfill({response}).catch(error=>console.error('Held response: '+error.message));
      } else await route.continue();
    };
    await p.route(pattern,handler);
    return {ready:async()=>{
      let timer;
      try { await Promise.race([ready,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Expected held request')),6000);})]); }
      finally {clearTimeout(timer);}
    },finish:async()=>{
      release();
      try {await p.waitForLoadState('networkidle');}
      catch(error) {throw Error(error.message+'; pending: '+[...pending].join(', '));}
      finally {
        await p.unroute(pattern,handler);
        p.off('request',track); p.off('requestfinished',done); p.off('requestfailed',done);
      }
    }};
  }
  function assertOne(title, assigned=false) {
    runPython(`from workpal.work.models import Issue, IssueRequirements
from workpal.actions.models import IdempotencyResult
from workpal.audit.models import AuditEvent, Outbox
from workpal.collaboration.models import Notification
i=Issue.objects.get(current_requirements__title=${JSON.stringify(title)})
assert IssueRequirements.objects.filter(issue=i).count()==1
assert IdempotencyResult.objects.filter(action_id='issue.create',result__data__id=i.pk).count()==1
assert AuditEvent.objects.filter(action_id='issue.create',fields__title=${JSON.stringify(title)}).count()==1
assert Outbox.objects.filter(action_id='issue.create',event__fields__title=${JSON.stringify(title)}).count()==1
assert Notification.objects.filter(issue=i).count()==${assigned?1:0}`);
  }
  function assertAbsent(title) {
    runPython(`from workpal.work.models import Issue
from workpal.audit.models import AuditEvent, Outbox
assert not Issue.objects.filter(current_requirements__title=${JSON.stringify(title)}).exists()
assert not AuditEvent.objects.filter(action_id='issue.create',fields__title=${JSON.stringify(title)}).exists()
assert not Outbox.objects.filter(action_id='issue.create',event__fields__title=${JSON.stringify(title)}).exists()`);
  }
  await test('dialog fits its own content width at desktop and mobile', async open => {
    const p=await open(); await issues(p); const d=await compose(p);
    for (const width of [1440,390]) {
      await p.setViewportSize({width,height:1000});
      assert(await d.evaluate(node=>node.scrollWidth<=node.clientWidth), 'dialog has horizontal overflow at '+width);
    }
  });
  await test('closed drafts retain selected names and distinct project identity', async open => {
    const p=await open(); await issues(p); const d=await compose(p,seed.second);
    await d.getByRole('button',{name:'reader (#2)',exact:true}).click();
    await p.keyboard.press('Escape');
    await p.getByRole('button',{name:'Create issue',exact:true}).click();
    await expect(d.locator('p').filter({hasText:`Duplicate (#${seed.second.id})`})).toHaveCount(1);
    await expect(d.locator('p').filter({hasText:'reader (#2)'})).toHaveCount(1);
  });
  await test('project and people selectors paginate after authorization and activity filters', async open => {
    const p=await open(); await issues(p); const d=await compose(p,null);
    for (const [name,query] of [['projects','Page'],['people','Person']]) {
      const section=d.locator('section').filter({has:p.getByLabel('Search '+name)});
      await d.getByLabel('Search '+name).fill(query);
      const choices=section.getByRole('button').filter({hasText:new RegExp('^'+query+' ')});
      await expect(choices).toHaveCount(20);
      await section.getByRole('button',{name:'Load more '+name,exact:true}).click();
      await expect(choices).toHaveCount(25);
      const texts=await choices.allTextContents(); assert.equal(new Set(texts).size,25);
      assert(texts.every(s=>!/(hidden|archived|inactive|foreign)/.test(s)));
      await d.getByLabel('Search '+name).fill(query+' 24');
      await expect(choices).toHaveCount(1);
      await expect(section.getByRole('button',{name:'Load more '+name,exact:true})).toBeHidden();
    }
  });
  await test('lost committed response retries one frozen intent after Escape and reopening', async open => {
    const p=await open(); await issues(p); const d=await compose(p,seed.normal,'Lost response');
    await d.getByRole('button',{name:'reader (#2)',exact:true}).click();
    const attempts=[];
    await p.route('**/api/v1/actions/issue.create',async route=>{
      attempts.push(route.request().postDataJSON());
      if(attempts.length===1){await route.fetch();await route.abort('failed');}else await route.continue();
    });
    await d.getByRole('button',{name:'Create issue',exact:true}).click();
    await expect(d.getByRole('button',{name:'Retry original request',exact:true})).toBeVisible();
    await expect(d.getByLabel('Title',{exact:true})).toBeDisabled();
    await p.keyboard.press('Escape'); await p.getByRole('button',{name:'Create issue',exact:true}).click();
    await expect(d.getByLabel('Title',{exact:true})).toHaveValue('Lost response');
    await expect(d.getByLabel('Title',{exact:true})).toBeDisabled();
    await d.getByRole('button',{name:'Retry original request',exact:true}).click();
    await expect(d).toHaveCount(0); await expect(p.locator('.issue-detail')).toContainText('Lost response');
    assert.equal(attempts.length,2); assert.deepEqual(attempts[0],attempts[1]); assertOne('Lost response',true);
  });
  await test('closing an in-flight create keeps its key and ignores the old dialog response', async open => {
    const p=await open(); await issues(p); const d=await compose(p,seed.normal,'Closed pending');
    const attempts=[]; p.on('request',r=>{if(r.url().endsWith('/actions/issue.create'))attempts.push(r.postDataJSON());});
    const held=await hold(p,'issue.create');
    try {
      await d.getByRole('button',{name:'Create issue',exact:true}).click(); await held.ready();
      await expect(d.getByRole('button',{name:'Create issue',exact:true})).toBeDisabled();
      await p.keyboard.press('Escape'); await p.getByRole('button',{name:'Create issue',exact:true}).click();
      await d.getByRole('button',{name:'Retry original request',exact:true}).click();
      await expect(d).toHaveCount(0); await expect(p.locator('.issue-detail')).toContainText('Closed pending');
    } finally {await held.finish();}
    assert.equal(attempts.length,2); assert.deepEqual(attempts[0],attempts[1]); assertOne('Closed pending');
  });
  await test('archiving the selected project preserves an editable draft on real 409', async open => {
    const p=await open(); await issues(p); const d=await compose(p,seed.archive,'Archived draft');
    runPython(`from workpal.work import service; from workpal.contracts import Actor
service.update(Actor(1,1),${seed.archive.id},1,archived=True)`);
    await d.getByRole('button',{name:'Create issue',exact:true}).click();
    await expect(d.getByRole('alert')).toContainText('Project archived');
    await expect(d.getByLabel('Title',{exact:true})).toBeEnabled();
    await expect(d.getByLabel('Title',{exact:true})).toHaveValue('Archived draft'); assertAbsent('Archived draft');
    await d.getByLabel('Search projects').fill('Normal');
    await d.getByRole('button',{name:`Normal (#${seed.normal.id})`,exact:true}).click();
    await d.getByRole('button',{name:'Create issue',exact:true}).click();
    await expect(d).toHaveCount(0); assertOne('Archived draft');
  });
  await test('directory visibility does not allow assignment without the project source', async open => {
    const p=await open(); await issues(p); const d=await compose(p,seed.private,'Denied assignee');
    await d.getByRole('button',{name:'reader (#2)',exact:true}).click();
    await d.getByRole('button',{name:'Create issue',exact:true}).click();
    await expect(p.getByRole('button',{name:'Refresh account',exact:true})).toBeVisible();
    await expect(d).toHaveCount(0); assertAbsent('Denied assignee');
  });
  await test('removed candidate and revoked project each reject without creating a record', async open => {
    for (const candidate of [true,false]) {
      const p=await open(); await issues(p); const title=candidate?'Candidate removed':'Project revoked';
      const d=await compose(p,candidate?seed.normal:seed.revocable,title);
      if(candidate){
        await d.getByLabel('Search people').fill('Revocable candidate');
        await d.getByRole('button',{name:`Revocable candidate (#${seed.candidate})`,exact:true}).click();
        runPython(`from workpal.identity.models import Membership; Membership.objects.filter(user_id=${seed.candidate},workspace_id=1).delete()`);
      }else runPython("from workpal.access.models import SourceGrant; SourceGrant.objects.filter(user_id=1,source__object_id='create-revocable').delete()");
      await d.getByRole('button',{name:'Create issue',exact:true}).click();
      await expect(p.getByRole('button',{name:'Refresh account',exact:true})).toBeVisible();
      await expect(d).toHaveCount(0); await expect(p.locator('.project-row')).toHaveCount(0); assertAbsent(title);
    }
  });
  await test('late project and person searches cannot replace newer results', async open => {
    const p=await open(); await issues(p); const d=await compose(p,null);
    for(const [name,action,prefix] of [['projects','project.list','Page'],['people','workspace.people.list','Person']]){
      const held=await hold(p,action,b=>b.payload.query===prefix+' 23');
      try{
        await d.getByLabel('Search '+name).fill(prefix+' 23'); await held.ready();
        await d.getByLabel('Search '+name).fill(prefix+' 24');
        await expect(d.getByRole('button',{name:new RegExp('^'+prefix+' 24 ')})).toBeVisible();
      }finally{await held.finish();}
      await expect(d.getByRole('button',{name:new RegExp('^'+prefix+' 23 ')})).toHaveCount(0);
    }
  });
  await test('creation list refresh cannot replace a newer selected Issue', async open => {
    const p=await open(); await issues(p); const d=await compose(p,seed.normal,'Refresh race');
    const held=await hold(p,'issue.list');
    try{
      await d.getByRole('button',{name:'Create issue',exact:true}).click(); await held.ready();
      await p.getByRole('button',{name:'Refresh issues',exact:true}).click();
      await p.getByRole('button',{name:`Existing selection (#${seed.existing.id})`,exact:true}).click();
      await expect(p.locator('.issue-detail')).toContainText('Existing selection');
    }finally{await held.finish();}
    await expect(p.locator('.issue-detail')).toContainText('Existing selection');
    await expect(p.locator('.issue-detail')).not.toContainText('Refresh race'); assertOne('Refresh race');
  });
  await test('a closed creation response cannot leak into a new workspace', async open => {
    const p=await open(); await issues(p); const d=await compose(p,seed.normal,'Old workspace creation');
    const held=await hold(p,'issue.create');
    try{
      await d.getByRole('button',{name:'Create issue',exact:true}).click(); await held.ready();
      await p.keyboard.press('Escape'); await p.getByLabel('Workspace',{exact:true}).selectOption('2');
      await p.getByRole('button',{name:'Issues',exact:true}).click();
      await expect(p.getByText('No issues found.',{exact:true})).toBeVisible();
    }finally{await held.finish();}
    await expect(p.getByText('Old workspace creation',{exact:true})).toHaveCount(0); assertOne('Old workspace creation');
  });
  await test('empty projects disable save and a successful picker retry clears the read error', async open => {
    const p=await open(); await issues(p,String(seed.empty)); const d=await compose(p,null);
    await expect(d.getByRole('button',{name:'Create issue',exact:true})).toBeDisabled();
    await expect(d.getByRole('button',{name:'owner (#1)',exact:true})).toBeVisible();
    await p.context().setOffline(true); await d.getByLabel('Search projects').fill('Retry');
    await expect(d.getByRole('alert')).toContainText('unknown');
    await p.context().setOffline(false); await d.getByRole('button',{name:'Retry',exact:true}).click();
    await expect(d.getByRole('button',{name:'Retry',exact:true})).toHaveCount(0);
    await expect(d.locator('[role=alert]')).toHaveText('');
  });
  await test('criterion limit is visible and long malicious content remains text on mobile', async open => {
    const p=await open({width:390,height:1000}); await issues(p); const d=await compose(p);
    await d.getByLabel('Title',{exact:true}).fill('<img src=x>'+ 'X'.repeat(289));
    await d.getByLabel('Description',{exact:true}).fill('<script>alert(1)</script>'+'Y'.repeat(19970));
    for(let n=1;n<=100;n++) await d.getByRole('button',{name:'Add criterion',exact:true}).click();
    await expect(d.getByRole('button',{name:'Add criterion',exact:true})).toBeDisabled();
    assert.equal(await p.locator('main img, dialog img, dialog script').count(),0);
    assert(await d.evaluate(node=>node.scrollWidth<=node.clientWidth));
    await d.getByRole('button',{name:'Remove criterion 50',exact:true}).click();
    await expect(d.getByRole('button',{name:'Add criterion',exact:true})).toBeEnabled();
  });
  assert.deepEqual(failures,[],'creation review scenarios');
});
