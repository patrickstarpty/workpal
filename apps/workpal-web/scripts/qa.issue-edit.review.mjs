import assert from 'node:assert/strict';
import {withBrowser, signIn} from './browser-fixture.mjs';

await withBrowser(async ({base, newPage, runPython, expect}) => {
  const parse=code=>JSON.parse(runPython(code).trim().split('\n').at(-1));
  const seed=parse(`
import json
from workpal.contracts import Actor,ObjectRef
from workpal.work import service,issues
from workpal.access.service import register_object
from workpal.access.models import SourceGrant,RegisteredObject
a=Actor(1,1); p=service.create(a,'Editing review'); data={}
for name in ['history','retry','pending','reload','readonly','revoke','other','workspace','refresh','ledger','criteria','long']:
    data[name]=issues.create(a,p['id'],'Edit '+name,description='Initial '+name,criteria=[{'key':'delivery_check','text':'Keep custom'},{'key':'criterion_3','text':'Original second'}],assignee_user_id=2 if name=='history' else 0)
for name in ['readonly','revoke']:
    ref=register_object(1,ObjectRef('source','edit-'+name),is_source=True)
    register_object(1,issues.requirement_ref(data[name]['requirements_version_id']),[ref])
    SourceGrant.objects.create(user_id=1,source=RegisteredObject.objects.get(kind=ref.kind,object_id=ref.id),read=True,write=name!='readonly')
print(json.dumps(data))`);
  const state=id=>parse(`import json
from workpal.work.models import Issue,IssueRequirements
from workpal.actions.models import IdempotencyResult
from workpal.audit.models import AuditEvent,Outbox
from workpal.collaboration.models import Notification
print(json.dumps(dict(issue=Issue.objects.values().get(pk=${id}),versions=list(IssueRequirements.objects.filter(issue_id=${id}).order_by('number').values()),updates=AuditEvent.objects.filter(action_id='issue.update',fields__issue_id=${id}).count(),outbox=Outbox.objects.filter(action_id='issue.update',event__fields__issue_id=${id}).count(),cache=IdempotencyResult.objects.filter(action_id='issue.update',result__data__id=${id}).count(),notifications=list(Notification.objects.filter(issue_id=${id}).order_by('pk').values())),default=str))`);
  const failures=[];
  async function test(name,run) {
    if(process.env.WORKPAL_QA_FILTER&&!new RegExp(process.env.WORKPAL_QA_FILTER).test(name))return;
    const pages=[];
    const open=async(viewport)=>{const p=await newPage(viewport);p.setDefaultTimeout(6000);pages.push(p);return p;};
    try{await run(open);console.log('PASS '+name);}catch(error){failures.push(name);console.error('FAIL '+name+'\n'+error.message);}
    finally{for(const p of pages)await p.context().close();}
  }
  async function select(p,item,username='owner') {
    await signIn(p,base,username);await p.getByLabel('Workspace',{exact:true}).selectOption('1');
    await p.getByRole('button',{name:'Issues',exact:true}).click();
    await p.getByLabel('Search issues').fill(item.title);
    await p.getByRole('button',{name:`${item.title} (#${item.id})`,exact:true}).click();
    await expect(p.getByRole('heading',{name:`Requirements version ${item.requirements_revision??1}`,exact:true})).toBeVisible();
  }
  async function edit(p) {
    await p.getByRole('button',{name:'Edit requirements',exact:true}).click();
    return p.getByRole('dialog',{name:'Edit requirements',exact:true});
  }
  async function save(d) {
    await d.getByRole('button',{name:'Save changes',exact:true}).click();await expect(d).toHaveCount(0);
  }
  async function hold(p,action,match=()=>true) {
    let release,arrived,used=false;
    const wait=new Promise(r=>{release=r;}),ready=new Promise(r=>{arrived=r;});
    const pattern='**/api/v1/actions/'+action;
    const fn=async route=>{
      if(!used&&match(route.request().postDataJSON())){used=true;const response=await route.fetch();arrived();await wait;await route.fulfill({response});}
      else await route.continue();
    };
    await p.route(pattern,fn);
    return {ready:async()=>{let timer;try{await Promise.race([ready,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Held request missing')),6000);})]);}finally{clearTimeout(timer);}},
      finish:async()=>{release();await p.waitForLoadState('networkidle');await p.unroute(pattern,fn);}};
  }
  function changedOnly(before,after,versions,updates) {
    const mutable=new Set(['revision','current_requirements_id','updated_at']);
    for(const key of Object.keys(before.issue))if(!mutable.has(key))assert.deepEqual(after.issue[key],before.issue[key],key+' stays unchanged');
    assert.deepEqual(after.notifications,before.notifications);
    assert.deepEqual(after.versions.slice(0,before.versions.length),before.versions,'history is immutable');
    assert.equal(after.versions.length,versions);assert.equal(after.updates,updates);
    assert.equal(after.outbox,updates);assert.equal(after.cache,updates);
  }
  await test('member edit preserves custom keys and metadata, history and new-context persistence',async open=>{
    const item=seed.history,p=await open();await select(p,item,'reader');const before=state(item.id);
    const d=await edit(p),requests=[];p.on('request',r=>{if(r.url().endsWith('/actions/issue.update'))requests.push(r.postDataJSON());});
    await d.getByRole('button',{name:'Save changes',exact:true}).click();
    await expect(d.getByRole('alert')).toHaveText('No changes to save');assert.equal(requests.length,0);assert.deepEqual(state(item.id),before);
    await d.getByLabel('Title',{exact:true}).fill('Edited <img src=x>');
    await d.getByLabel('Description',{exact:true}).fill('Stored description');
    await d.getByRole('button',{name:'Remove criterion 2',exact:true}).click();
    await d.getByRole('button',{name:'Add criterion',exact:true}).click();
    await d.getByLabel('Acceptance criterion 4',{exact:true}).fill('New item');await save(d);
    const after=state(item.id);changedOnly(before,after,2,1);assert.equal(after.issue.revision,2);
    assert.deepEqual(after.versions[1].criteria,[{key:'delivery_check',text:'Keep custom'},{key:'criterion_4',text:'New item'}]);
    const fresh=await open();await select(fresh,{...item,title:'Edited <img src=x>',requirements_revision:2},'reader');
    await expect(fresh.locator('.issue-detail')).toContainText('Stored description');
    assert.equal(await fresh.locator('main img').count(),0);
    await fresh.getByRole('button',{name:'Previous version',exact:true}).click();
    await expect(fresh.getByRole('heading',{name:'Requirements version 1',exact:true})).toBeVisible();
    await expect(fresh.getByRole('region',{name:'Requirements history'})).toContainText('Original second');
    const empty=await edit(fresh);await empty.getByLabel('Description',{exact:true}).fill('');
    await empty.getByRole('button',{name:'Remove criterion 1',exact:true}).click();await empty.getByRole('button',{name:'Remove criterion 2',exact:true}).click();await save(empty);
    const cleared=state(item.id);changedOnly(before,cleared,3,2);
    assert.equal(cleared.versions[2].description,'');assert.deepEqual(cleared.versions[2].criteria,[]);
    assert.deepEqual(Object.keys(requests[0].payload).sort(),['criteria','description','issue_id','title']);
  });
  await test('lost edit response replays exact revision and key even after a newer version exists',async open=>{
    const item=seed.retry,a=await open();await select(a,item);const d=await edit(a);
    const attempts=[];await a.route('**/api/v1/actions/issue.update',async route=>{
      attempts.push(route.request().postDataJSON());if(attempts.length===1){await route.fetch();await route.abort('failed');}else await route.continue();
    });
    await d.getByLabel('Title',{exact:true}).fill('Lost edit');await d.getByRole('button',{name:'Save changes',exact:true}).click();
    await expect(d.getByRole('button',{name:'Retry original request',exact:true})).toBeVisible();
    await expect(d.getByLabel('Title',{exact:true})).toBeDisabled();
    await expect(d.getByRole('button',{name:'Reload current',exact:true,includeHidden:true})).toBeDisabled();
    const b=await open();await select(b,{...item,title:'Lost edit',requirements_revision:2});const db=await edit(b);
    await db.getByLabel('Description',{exact:true}).fill('Newer saved description');await save(db);
    await a.keyboard.press('Escape');await edit(a);await d.getByRole('button',{name:'Retry original request',exact:true}).click();await expect(d).toHaveCount(0);
    await expect(a.locator('.issue-detail')).toContainText('Newer saved description');
    assert.equal(attempts.length,2);assert.deepEqual(attempts[0],attempts[1]);assert.equal(attempts[1].expected_revision,1);
    const facts=state(item.id);assert.equal(facts.versions.length,3);assert.equal(facts.updates,2);assert.equal(facts.cache,2);assert.equal(facts.outbox,2);
  });
  await test('closing an in-flight save permits original retry and ignores the old dialog result',async open=>{
    const item=seed.pending,p=await open();await select(p,item);const d=await edit(p);
    await d.getByLabel('Description',{exact:true}).fill('Pending description');const attempts=[];
    p.on('request',r=>{if(r.url().endsWith('/actions/issue.update'))attempts.push(r.postDataJSON());});
    const held=await hold(p,'issue.update');
    try{
      await d.getByRole('button',{name:'Save changes',exact:true}).click();await held.ready();await p.keyboard.press('Escape');await edit(p);
      await expect(d.getByRole('button',{name:'Retry original request',exact:true})).toBeEnabled();
    }finally{await held.finish();}
    await expect(d).toBeVisible();await expect(d.getByLabel('Description',{exact:true})).toHaveValue('Pending description');
    await d.getByRole('button',{name:'Retry original request',exact:true}).click();await expect(d).toHaveCount(0);
    assert.equal(attempts.length,2);assert.deepEqual(attempts[0],attempts[1]);assert.equal(state(item.id).versions.length,2);
  });
  await test('closing a conflict reload cannot replace the reopened draft or its hidden baseline',async open=>{
    const item=seed.reload,a=await open(),b=await open();await select(a,item);await select(b,item);
    const da=await edit(a),db=await edit(b);await da.getByLabel('Description',{exact:true}).fill('Local before close');
    await db.getByLabel('Title',{exact:true}).fill('Remote changed');await save(db);
    await da.getByRole('button',{name:'Save changes',exact:true}).click();await expect(da.getByRole('button',{name:'Save changes',exact:true})).toBeDisabled();
    const held=await hold(a,'issue.read');
    try{
      await da.getByRole('button',{name:'Reload current',exact:true}).click();await held.ready();await a.keyboard.press('Escape');await edit(a);
      await expect(da.getByRole('button',{name:'Reload current',exact:true})).toBeEnabled();
    }finally{await held.finish();}
    await expect(da.getByLabel('Title',{exact:true})).toHaveValue(item.title);
    await da.getByLabel('Description',{exact:true}).fill('Kept after close');
    await da.getByRole('button',{name:'Reload current',exact:true}).click();
    await expect(da.getByLabel('Title',{exact:true})).toHaveValue('Remote changed');await expect(da.getByLabel('Description',{exact:true})).toHaveValue('Kept after close');
    await save(da);const facts=state(item.id);assert.equal(facts.versions[2].description,'Kept after close');assert.equal(facts.versions[2].title,'Remote changed');
  });
  await test('conflict reload never reuses a criterion key consumed earlier in this draft',async open=>{
    const item=seed.ledger,a=await open(),b=await open();await select(a,item);await select(b,item);
    const da=await edit(a),db=await edit(b);
    await da.getByRole('button',{name:'Add criterion',exact:true}).click();await da.getByLabel('Acceptance criterion 4',{exact:true}).fill('Temporary');
    await da.getByRole('button',{name:'Remove criterion 4',exact:true}).click();await da.getByLabel('Description',{exact:true}).fill('Local description');
    await db.getByLabel('Title',{exact:true}).fill('Ledger remote');await save(db);
    await da.getByRole('button',{name:'Save changes',exact:true}).click();await da.getByRole('button',{name:'Reload current',exact:true}).click();
    await expect(da.getByLabel('Title',{exact:true})).toHaveValue('Ledger remote');
    await da.getByRole('button',{name:'Add criterion',exact:true}).click();
    await da.getByLabel('Acceptance criterion 5',{exact:true}).fill('New stable item');await save(da);
    assert.equal(state(item.id).versions.at(-1).criteria.at(-1).key,'criterion_5');
  });
  await test('criteria conflicts retain local array and show the current saved comparison',async open=>{
    const item=seed.criteria,a=await open(),b=await open();await select(a,item);await select(b,item);
    const da=await edit(a),db=await edit(b);
    await da.getByLabel('Acceptance criterion 1',{exact:true}).fill('Remote standard');await save(da);
    await db.getByLabel('Acceptance criterion 2',{exact:true}).fill('Local standard');await db.getByRole('button',{name:'Save changes',exact:true}).click();
    await db.getByRole('button',{name:'Reload current',exact:true}).click();
    await expect(db.getByRole('heading',{name:'Current saved requirements',exact:true})).toBeVisible();
    await expect(db.getByLabel('Acceptance criterion 1',{exact:true})).toHaveValue('Keep custom');
    await expect(db.getByText('Remote standard',{exact:true})).toBeVisible();
    await expect(db.getByLabel('Acceptance criterion 2',{exact:true})).toHaveValue('Local standard');await save(db);
    const facts=state(item.id);assert.equal(facts.versions.length,3);assert.equal(facts.versions[1].criteria[0].text,'Remote standard');assert.equal(facts.versions[2].criteria[1].text,'Local standard');
  });
  await test('read-only and revoked independent requirements block content updates without changing facts',async open=>{
    for(const name of ['readonly','revoke']){
      const item=seed[name],p=await open();await select(p,item);const d=await edit(p);await d.getByLabel('Title',{exact:true}).fill('Forbidden change');
      if(name==='revoke')runPython("from workpal.access.models import SourceGrant; SourceGrant.objects.filter(source__object_id='edit-revoke',user_id=1).delete()");
      const before=state(item.id);await d.getByRole('button',{name:'Save changes',exact:true}).click();
      await expect(p.getByRole('button',{name:'Refresh account',exact:true})).toBeVisible();await expect(d).toHaveCount(0);await expect(p.locator('.issue-detail')).toHaveCount(0);
      assert.deepEqual(state(item.id),before);
    }
  });
  await test('pending edit cannot reopen a former Issue after selecting another one',async open=>{
    const item=seed.other,p=await open();await select(p,item);const d=await edit(p);await d.getByLabel('Description',{exact:true}).fill('Old pending');
    const held=await hold(p,'issue.update');
    try{
      await d.getByRole('button',{name:'Save changes',exact:true}).click();await held.ready();await p.keyboard.press('Escape');
      await p.getByLabel('Search issues').fill(seed.long.title);await p.getByRole('button',{name:`${seed.long.title} (#${seed.long.id})`,exact:true}).click();
      await expect(p.locator('.issue-detail')).toContainText(seed.long.title);
    }finally{await held.finish();}
    await expect(p.locator('.issue-detail')).not.toContainText('Old pending');await expect(p.locator('dialog')).toHaveCount(0);
  });
  await test('pending edit cannot leak into a different workspace',async open=>{
    const item=seed.workspace,p=await open();await select(p,item);const d=await edit(p);await d.getByLabel('Description',{exact:true}).fill('Other scope pending');
    const held=await hold(p,'issue.update');
    try{
      await d.getByRole('button',{name:'Save changes',exact:true}).click();await held.ready();await p.keyboard.press('Escape');
      await p.getByLabel('Workspace',{exact:true}).selectOption('2');await p.getByRole('button',{name:'Issues',exact:true}).click();
      await expect(p.getByText('No issues found.',{exact:true})).toBeVisible();
    }finally{await held.finish();}
    await expect(p.getByText('Other scope pending',{exact:true})).toHaveCount(0);await expect(p.locator('dialog')).toHaveCount(0);
  });
  await test('post-save list refresh does not override a new selection',async open=>{
    const item=seed.refresh,p=await open();await select(p,item);await p.getByLabel('Search issues').fill('');
    await p.getByRole('button',{name:`${item.title} (#${item.id})`,exact:true}).click();const d=await edit(p);
    await d.getByLabel('Description',{exact:true}).fill('Saved refresh race');const held=await hold(p,'issue.list');
    try{
      await d.getByRole('button',{name:'Save changes',exact:true}).click();await held.ready();
      await p.getByRole('button',{name:'Refresh issues',exact:true}).click();
      await p.getByRole('button',{name:`${seed.long.title} (#${seed.long.id})`,exact:true}).click();
      await expect(p.locator('.issue-detail')).toContainText(seed.long.title);
    }finally{await held.finish();}
    await expect(p.locator('.issue-detail')).not.toContainText('Saved refresh race');
  });
  await test('blank inputs do not write and long malicious drafts fit the dialog',async open=>{
    const item=seed.long,p=await open({width:390,height:1000});await select(p,item);const d=await edit(p),before=state(item.id);
    await d.getByLabel('Title',{exact:true}).fill('   ');await d.getByRole('button',{name:'Save changes',exact:true}).click();
    await expect(d.getByRole('alert')).toContainText('Enter a title');assert.deepEqual(state(item.id),before);
    await d.getByLabel('Title',{exact:true}).fill('<img src=x>'+'X'.repeat(289));
    await d.getByLabel('Description',{exact:true}).fill('<script>alert(1)</script>'+'Y'.repeat(19970));
    assert(await d.evaluate(node=>node.scrollWidth<=node.clientWidth));assert.equal(await d.locator('img,script').count(),0);
    await p.keyboard.press('Escape');await expect(p.getByRole('button',{name:'Edit requirements',exact:true})).toBeFocused();
    await edit(p);await expect(d.getByLabel('Title',{exact:true})).toHaveValue('<img src=x>'+'X'.repeat(289));
  });
  assert.deepEqual(failures,[],'requirements editor review');
});
