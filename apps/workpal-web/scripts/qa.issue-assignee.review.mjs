import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {withBrowser,signIn} from './browser-fixture.mjs';

await withBrowser(async ({base,newPage,runPython,expect,repo})=>{
  const parse=code=>JSON.parse(runPython(code).trim().split('\n').at(-1));
  const seed=parse(`import json
from django.contrib.auth import get_user_model
from workpal.identity.models import Membership
from workpal.contracts import Actor,ObjectRef
from workpal.work import issues,service
from workpal.access.service import register_object
from workpal.access.models import SourceGrant,RegisteredObject
a=Actor(1,1);p=service.create(a,'Assignment review');people=[];data={}
for name in ['Member'+str(n).zfill(2) for n in range(22)]+['Withdraw candidate','Inactive candidate','Missing assignee','<img src=x>'+'X'*139]:
    u=get_user_model().objects.create_user(username=name);Membership.objects.create(user=u,workspace_id=1,role='member');people.append({'user_id':u.pk,'username':u.username})
for name in ['core','conflict','same','retry','pending','reload','readonly','deniedIssue','deniedReq','withdraw','inactive','revokedActor','revokedReq','replayRevoke','navigation','workspace','refresh','label','picker','missing','malicious']:
    target=people[21]['user_id'] if name=='core' else people[24]['user_id'] if name=='missing' else people[25]['user_id'] if name=='malicious' else 2 if name=='label' else 0
    data[name]=issues.create(a,p['id'],'Assign '+name,description='Preserve '+name,criteria=[{'key':'stable','text':'Original criterion'}],assignee_user_id=target)
data['core']=issues.update(a,data['core']['id'],1,description='Second requirements version')
for name in ['readonly','deniedIssue','deniedReq','revokedReq','replayRevoke']:
    ref=register_object(1,ObjectRef('source','assignee-'+name),is_source=True)
    register_object(1,issues.ref(data[name]['id']) if name=='deniedIssue' else issues.requirement_ref(data[name]['requirements_version_id']),[ref])
    row=RegisteredObject.objects.get(kind=ref.kind,object_id=ref.id)
    SourceGrant.objects.create(user_id=1,source=row,read=True,write=name!='readonly')
    if name not in ['deniedIssue','deniedReq']:SourceGrant.objects.create(user_id=2,source=row,read=True)
Membership.objects.filter(user_id=people[24]['user_id'],workspace_id=1).delete()
print(json.dumps({'issues':data,'people':people}))`);
  const items=seed.issues,people=seed.people,failures=[];
  const state=id=>parse(`import json
from workpal.work.models import Issue,IssueRequirements
from workpal.collaboration.models import Notification
from workpal.actions.models import IdempotencyResult
from workpal.audit.models import AuditEvent,Outbox
print(json.dumps(dict(issue=Issue.objects.values().get(pk=${id}),versions=list(IssueRequirements.objects.filter(issue_id=${id}).order_by('number').values()),notifications=list(Notification.objects.filter(issue_id=${id}).order_by('pk').values()),audit=AuditEvent.objects.filter(action_id='issue.update',fields__issue_id=${id}).count(),outbox=Outbox.objects.filter(action_id='issue.update',event__fields__issue_id=${id}).count(),cache=IdempotencyResult.objects.filter(action_id='issue.update',result__data__id=${id}).count()),default=str))`);
  async function test(name,run){
    if(process.env.WORKPAL_QA_FILTER&&!new RegExp(process.env.WORKPAL_QA_FILTER).test(name))return;
    const pages=[],open=async viewport=>{const p=await newPage(viewport);p.setDefaultTimeout(6000);pages.push(p);return p;};
    try{await run(open);console.log('PASS '+name);}catch(e){failures.push(name);console.error('FAIL '+name+'\n'+e.message);}
    finally{for(const p of pages)await p.context().close();}
  }
  async function select(p,item,username='owner'){
    await signIn(p,base,username);await p.getByLabel('Workspace',{exact:true}).selectOption('1');await p.getByRole('button',{name:'Issues',exact:true}).click();
    await p.getByLabel('Search issues').fill(item.title);await p.getByRole('button',{name:`${item.title} (#${item.id})`,exact:true}).click();
    await expect(p.getByRole('heading',{name:`Requirements version ${item.requirements_revision}`,exact:true})).toBeVisible();
  }
  async function editor(p){await p.getByRole('button',{name:'Change assignee',exact:true}).click();return p.getByRole('dialog',{name:'Change assignee',exact:true});}
  const chosen=d=>d.locator('fieldset section > p').first();
  const currentPerson=d=>d.locator('form > div').filter({hasText:'Current assignee'});
  async function pick(d,id){
    const person=id===1?{username:'owner',user_id:1}:id===2?{username:'reader',user_id:2}:people.find(p=>p.user_id===id);
    if(!id){await d.getByRole('button',{name:'Unassigned',exact:true}).click();await expect(chosen(d)).toHaveText('Unassigned');return;}
    await d.getByLabel('Search people').fill(person.username);await d.getByRole('button',{name:`${person.username} (#${id})`,exact:true}).click();
    await expect(chosen(d)).toHaveText(`${person.username} (#${id})`);
  }
  async function save(d){await d.getByRole('button',{name:'Save assignee',exact:true}).click();await expect(d).toHaveCount(0);}
  function track(p){const requests=[];p.on('request',r=>{if(r.url().endsWith('/actions/issue.update'))requests.push(r.postDataJSON());});return requests;}
  async function hold(p,action,match=()=>true){
    let release,arrived,used=false;const gate=new Promise(r=>release=r),ready=new Promise(r=>arrived=r),pattern='**/api/v1/actions/'+action;
    const fn=async route=>{if(used||!match(route.request().postDataJSON()))return route.continue();used=true;const response=await route.fetch();arrived();await gate;await route.fulfill({response});};
    await p.route(pattern,fn);return {ready:async()=>{let timer;try{await Promise.race([ready,new Promise((_,reject)=>timer=setTimeout(()=>reject(Error('Held request missing')),6000))]);}finally{clearTimeout(timer);}},finish:async()=>{release();await p.waitForLoadState('networkidle');await p.unroute(pattern,fn);}};
  }
  async function lose(p){const attempts=[];await p.route('**/api/v1/actions/issue.update',async route=>{attempts.push(route.request().postDataJSON());if(attempts.length===1){const r=await route.fetch();assert.equal(r.status(),200);await route.abort('failed');}else await route.continue();});return attempts;}
  function unchangedRequirements(before,after,writes,notifications){
    for(const key of Object.keys(before.issue))if(!['assignee_id','revision','updated_at'].includes(key))assert.deepEqual(after.issue[key],before.issue[key],key);
    assert.deepEqual(after.versions,before.versions);assert.equal(after.issue.revision,before.issue.revision+writes);
    for(const key of ['audit','outbox','cache'])assert.equal(after[key],before[key]+writes,key);
    assert.equal(after.notifications.length,before.notifications.length+notifications);
    for(const old of before.notifications)assert.deepEqual(after.notifications.find(n=>n.id===old.id),old);
  }

  await test('member assignment persists and changes only ownership with exact notifications and events',async open=>{
    const item=items.core,p=await open();await select(p,item,'reader');const before=state(item.id),requests=track(p);
    await expect(p.locator('.issue-detail')).toContainText('Member21 (#24)');const d=await editor(p);
    await d.getByRole('button',{name:'Save assignee',exact:true}).click();await expect(d.getByRole('alert')).toHaveText('No changes to save');assert.equal(requests.length,0);assert.deepEqual(state(item.id),before);
    await pick(d,1);await p.keyboard.press('Escape');await expect(p.getByRole('button',{name:'Change assignee',exact:true})).toBeFocused();await editor(p);await expect(chosen(d)).toHaveText('owner (#1)');await save(d);
    await expect(p.locator('.issue-detail')).toContainText('Assignee: owner (#1)');const assigned=state(item.id);unchangedRequirements(before,assigned,1,1);assert.equal(assigned.issue.assignee_id,1);
    const notice=assigned.notifications.find(n=>!before.notifications.some(old=>old.id===n.id));assert.equal(notice.recipient_id,1);assert.equal(notice.kind,'assignment');assert.equal(notice.event_key,`issue:${item.id}:assignment:${assigned.issue.revision}`);
    assert.deepEqual(requests[0].payload,{issue_id:item.id,assignee_user_id:1});assert.equal(requests[0].expected_revision,before.issue.revision);
    const fresh=await open();await select(fresh,item,'reader');await expect(fresh.locator('.issue-detail')).toContainText('Assignee: owner (#1)');
    await fresh.getByRole('button',{name:'Previous version',exact:true}).click();await expect(fresh.getByRole('region',{name:'Requirements history'})).toContainText('Original criterion');
    const clear=await editor(fresh);await pick(clear,0);await save(clear);await expect(fresh.locator('.issue-detail')).toContainText('Assignee: Unassigned');
    const after=state(item.id);unchangedRequirements(before,after,2,1);assert.equal(after.issue.assignee_id,null);
  });
  for(const same of [false,true])await test(`concurrent assignment reload ${same?'recognizes the reached target without writing':'preserves the local target for explicit saving'}`,async open=>{
    const item=items[same?'same':'conflict'],a=await open(),b=await open();await select(a,item);await select(b,item);const before=state(item.id);
    const da=await editor(a),db=await editor(b),target= same?2:people[0].user_id,requests=track(b);
    await pick(db,target);await pick(da,2);await save(da);await db.getByRole('button',{name:'Save assignee',exact:true}).click();await expect(db.getByRole('button',{name:'Reload current',exact:true})).toBeVisible();
    await expect(chosen(db)).toContainText(same?'reader':'Member00');await db.getByRole('button',{name:'Reload current',exact:true}).click();await expect(currentPerson(db)).toContainText('reader (#2)');
    if(same){await expect(db.getByRole('alert')).toHaveText('No changes to save');await db.getByRole('button',{name:'Refresh issue',exact:true}).click();}
    else await save(db);
    await expect(db).toHaveCount(0);await expect(b.locator('.issue-detail')).toContainText(same?'Assignee: reader (#2)':'Assignee: Member00 (#3)');
    unchangedRequirements(before,state(item.id),same?1:2,same?1:2);assert.equal(requests.length,same?1:2);
    if(!same){assert.equal(requests[1].expected_revision,before.issue.revision+1);assert.notEqual(requests[0].idempotency_key,requests[1].idempotency_key);}
  });
  await test('lost assignment replays original intent after a newer reassignment and reads current facts',async open=>{
    const item=items.retry,a=await open();await select(a,item);const before=state(item.id),d=await editor(a),attempts=await lose(a);await pick(d,2);
    await d.getByRole('button',{name:'Save assignee',exact:true}).click();await expect(d.getByRole('button',{name:'Retry original request',exact:true})).toBeEnabled();await expect(d.getByLabel('Search people')).toBeDisabled();
    const b=await open();await select(b,item);const db=await editor(b);await pick(db,people[0].user_id);await save(db);
    await a.keyboard.press('Escape');await editor(a);await expect(chosen(d)).toHaveText('reader (#2)');await d.getByRole('button',{name:'Retry original request',exact:true}).click();await expect(d).toHaveCount(0);
    await expect(a.locator('.issue-detail')).toContainText('Assignee: Member00 (#3)');assert.equal(attempts.length,2);assert.deepEqual(attempts[0],attempts[1]);unchangedRequirements(before,state(item.id),2,2);
  });
  await test('in-flight save can be retried after closing without old responses closing the new dialog',async open=>{
    const item=items.pending,p=await open();await select(p,item);const before=state(item.id),d=await editor(p),requests=track(p);await pick(d,2);const held=await hold(p,'issue.update');
    try{await d.getByRole('button',{name:'Save assignee',exact:true}).click();await held.ready();await p.keyboard.press('Escape');await editor(p);await expect(d.getByRole('button',{name:'Retry original request',exact:true})).toBeEnabled();}finally{await held.finish();}
    await expect(d).toBeVisible();await d.getByRole('button',{name:'Retry original request',exact:true}).click();await expect(d).toHaveCount(0);assert.deepEqual(requests[0],requests[1]);unchangedRequirements(before,state(item.id),1,1);
  });
  await test('closing a conflict reload preserves the target and rejects the old baseline response',async open=>{
    const item=items.reload,a=await open(),b=await open();await select(a,item);await select(b,item);const da=await editor(a),db=await editor(b);await pick(da,people[0].user_id);await pick(db,2);await save(db);
    await da.getByRole('button',{name:'Save assignee',exact:true}).click();await expect(da.getByRole('button',{name:'Reload current',exact:true})).toBeVisible();const held=await hold(a,'issue.read');
    try{await da.getByRole('button',{name:'Reload current',exact:true}).click();await held.ready();await a.keyboard.press('Escape');await editor(a);await expect(da.getByRole('button',{name:'Reload current',exact:true})).toBeEnabled();}finally{await held.finish();}
    await expect(currentPerson(da)).toContainText('Unassigned');await expect(chosen(da)).toHaveText('Member00 (#3)');await da.getByRole('button',{name:'Reload current',exact:true}).click();await expect(currentPerson(da)).toContainText('reader (#2)');await save(da);assert.equal(state(item.id).issue.assignee_id,3);
  });
  await test('read-only requirements allow reassignment without changing their history',async open=>{
    const item=items.readonly,p=await open();await select(p,item);const before=state(item.id),d=await editor(p);await pick(d,2);await save(d);unchangedRequirements(before,state(item.id),1,1);
  });
  await test('candidate access, membership and activity failures preserve every assignment fact',async open=>{
    for(const name of ['deniedIssue','deniedReq','withdraw','inactive']){
      const item=items[name],p=await open();await select(p,item);const d=await editor(p),candidate=name==='withdraw'?people[22].user_id:name==='inactive'?people[23].user_id:2;await pick(d,candidate);
      if(name==='withdraw')runPython(`from workpal.identity.models import Membership;Membership.objects.filter(user_id=${candidate},workspace_id=1).delete()`);
      if(name==='inactive')runPython(`from django.contrib.auth import get_user_model;get_user_model().objects.filter(pk=${candidate}).update(is_active=False)`);
      const before=state(item.id),response=p.waitForResponse(r=>r.url().endsWith('/actions/issue.update'));
      await d.getByRole('button',{name:'Save assignee',exact:true}).click();assert.equal((await response).status(),name.startsWith('denied')?403:404);
      await expect(p.getByRole('button',{name:'Refresh account',exact:true})).toBeVisible();await expect(d).toHaveCount(0);assert.deepEqual(state(item.id),before);
    }
  });
  await test('requester revocation and revoked requirements reject saves and cached retries',async open=>{
    for(const name of ['revokedActor','revokedReq','replayRevoke']){
      const item=items[name],p=await open();await select(p,item);const d=await editor(p);await pick(d,2);
      if(name==='replayRevoke'){await lose(p);await d.getByRole('button',{name:'Save assignee',exact:true}).click();await expect(d.getByRole('button',{name:'Retry original request',exact:true})).toBeEnabled();}
      if(name==='revokedActor')runPython("from workpal.identity.models import Membership;Membership.objects.filter(user_id=1,workspace_id=1).delete()");
      else runPython(`from workpal.access.models import SourceGrant;SourceGrant.objects.filter(user_id=1,source__object_id='assignee-${name}').delete()`);
      const before=state(item.id);
      try{await d.getByRole('button',{name:name==='replayRevoke'?'Retry original request':'Save assignee',exact:true}).click();await expect(p.getByRole('button',{name:'Refresh account',exact:true})).toBeVisible();assert.deepEqual(state(item.id),before);}
      finally{if(name==='revokedActor')runPython("from workpal.identity.models import Membership;Membership.objects.create(user_id=1,workspace_id=1,role='owner')");}
    }
  });
  await test('person label network failure stays local and Retry recovers the current name',async open=>{
    const item=items.label,p=await open();let failed=false;
    await p.route('**/api/v1/actions/workspace.people.read',async r=>{if(!failed){failed=true;return r.abort('failed');}await r.continue();});
    const before=state(item.id);await select(p,item);await expect(p.getByRole('heading',{name:'Requirements version 1',exact:true})).toBeVisible();
    await p.locator('.issue-detail').getByRole('button',{name:'Retry',exact:true}).click();await expect(p.locator('.issue-detail')).toContainText('Assignee: reader (#2)');assert.deepEqual(state(item.id),before);
  });
  await test('late selected-person and directory search responses cannot replace the latest choice',async open=>{
    const item=items.picker,p=await open();await select(p,item);const d=await editor(p),held=await hold(p,'workspace.people.read',r=>r.payload.user_id===2);
    try{await d.getByRole('button',{name:'reader (#2)',exact:true}).click();await held.ready();await pick(d,people[0].user_id);}finally{await held.finish();}
    await expect(chosen(d)).toHaveText('Member00 (#3)');const search=await hold(p,'workspace.people.list',r=>r.payload.query==='Member');
    try{await d.getByLabel('Search people').fill('Member');await search.ready();await d.getByLabel('Search people').fill('owner');await expect(d.locator('.issue-picker-option button')).toHaveText(['owner (#1)']);}finally{await search.finish();}
    await expect(d.locator('.issue-picker-option button')).toHaveText(['owner (#1)']);await expect(chosen(d)).toHaveText('Member00 (#3)');await save(d);assert.equal(state(item.id).issue.assignee_id,3);
  });
  await test('unavailable current assignee remains distinct from Unassigned until explicitly changed',async open=>{
    const item=items.missing,p=await open();await select(p,item);await expect(p.locator('.issue-detail')).toContainText(`Unavailable person (#${people[24].user_id})`);
    const before=state(item.id),d=await editor(p),requests=track(p);await expect(chosen(d)).toContainText('Unavailable person');await d.getByRole('button',{name:'Save assignee',exact:true}).click();await expect(d.getByRole('alert')).toHaveText('No changes to save');assert.equal(requests.length,0);
    await pick(d,0);await save(d);unchangedRequirements(before,state(item.id),1,0);assert.equal(state(item.id).issue.assignee_id,null);
  });
  for(const workspace of [false,true])await test(`pending assignment cannot reopen ${workspace?'another workspace':'another Issue'}`,async open=>{
    const item=items[workspace?'workspace':'navigation'],p=await open();await select(p,item);const d=await editor(p);await pick(d,2);const held=await hold(p,'issue.update');
    try{await d.getByRole('button',{name:'Save assignee',exact:true}).click();await held.ready();await p.keyboard.press('Escape');
      if(workspace){await p.getByLabel('Workspace',{exact:true}).selectOption('2');await p.getByRole('button',{name:'Issues',exact:true}).click();await expect(p.getByText('No issues found.',{exact:true})).toBeVisible();}
      else{await p.getByLabel('Search issues').fill(items.malicious.title);await p.getByRole('button',{name:`${items.malicious.title} (#${items.malicious.id})`,exact:true}).click();await expect(p.locator('.issue-detail')).toContainText(items.malicious.title);}
    }finally{await held.finish();}
    await expect(p.locator('dialog')).toHaveCount(0);await expect(p.locator('.issue-detail')).not.toContainText(item.title);
  });
  await test('post-save refresh cannot replace a newer detail selection',async open=>{
    const item=items.refresh,p=await open();await select(p,item);const d=await editor(p);await pick(d,2);const held=await hold(p,'issue.list');
    try{await d.getByRole('button',{name:'Save assignee',exact:true}).click();await held.ready();await p.getByLabel('Search issues').fill(items.malicious.title);await p.getByRole('button',{name:`${items.malicious.title} (#${items.malicious.id})`,exact:true}).click();await expect(p.locator('.issue-detail')).toContainText(items.malicious.title);}finally{await held.finish();}
    await expect(p.locator('.issue-detail')).toContainText(items.malicious.title);await expect(p.locator('.issue-detail')).not.toContainText(item.title);
  });
  await test('long untrusted usernames fit the dialog and remain text at desktop and mobile sizes',async open=>{
    const item=items.malicious,p=await open();await select(p,item);const before=state(item.id),d=await editor(p);await expect(chosen(d)).toContainText(people[25].username);
    await mkdir(repo+'/outputs/workpal-web',{recursive:true});
    for(const [name,width] of [['desktop',1440],['mobile',390]]){
      await p.setViewportSize({width,height:1000});assert(await d.evaluate(node=>node.scrollWidth<=node.clientWidth));assert.equal(await d.locator('img,script').count(),0);
      await p.screenshot({path:repo+`/outputs/workpal-web/a54b5-assignee-${name}.png`});
    }
    await p.keyboard.press('Escape');await expect(p.getByRole('button',{name:'Change assignee',exact:true})).toBeFocused();assert.deepEqual(state(item.id),before);
  });
  assert.deepEqual(failures,[],'assignment review');
});
