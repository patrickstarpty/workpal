import assert from 'node:assert/strict';
import {withBrowser, signIn} from './browser-fixture.mjs';

await withBrowser(async ({base,newPage,runPython,expect}) => {
  const parse = code => JSON.parse(runPython(code).trim().split('\n').at(-1));
  const seed = parse(`import json
from workpal.contracts import Actor,ObjectRef
from workpal.work import issues,service
from workpal.access.service import register_object
from workpal.access.models import RegisteredObject,SourceGrant
a=Actor(1,1);p=service.create(a,'Archive review');data={}
for name in ['issue-readonly','req-readonly','issue-revoke','req-revoke','replay-revoke','reverse','restore-reverse','reload','facts','other','workspace','refresh','long']:
    data[name]=issues.create(a,p['id'],'Archive '+name,description='Original '+name,criteria=[{'key':'custom','text':'Preserved criterion'}])
for name in ['issue-readonly','req-readonly','issue-revoke','req-revoke','replay-revoke']:
    ref=register_object(1,ObjectRef('source','archive-'+name),is_source=True)
    obj=issues.ref(data[name]['id']) if name.startswith('issue-') else issues.requirement_ref(data[name]['requirements_version_id'])
    register_object(1,obj,[ref]);SourceGrant.objects.create(user_id=1,source=RegisteredObject.objects.get(kind=ref.kind,object_id=ref.id),read=True,write=not name.endswith('readonly'))
data['restore-reverse']=issues.archive(a,data['restore-reverse']['id'],1)
data['long']=issues.update(a,data['long']['id'],1,title='<img src=x>'+'X'*289)
data['pages']=[]
for n in range(26):
    item=issues.create(a,p['id'],'Page archive '+str(n))
    if n in [0,10,25]:
        ref=register_object(1,ObjectRef('source','archive-private-'+str(n)),is_source=True)
        register_object(1,issues.requirement_ref(item['requirements_version_id']),[ref])
    else:data['pages'].append(item)
print(json.dumps(data))`);
  const state = id => parse(`import json
from workpal.work.models import Issue,IssueRequirements
from workpal.audit.models import AuditEvent,Outbox
from workpal.actions.models import IdempotencyResult
from workpal.collaboration.models import Notification
print(json.dumps(dict(issue=Issue.objects.values().get(pk=${id}),versions=list(IssueRequirements.objects.filter(issue_id=${id}).order_by('number').values()),notifications=list(Notification.objects.filter(issue_id=${id}).values()),counts={a:[AuditEvent.objects.filter(action_id=a,fields__issue_id=${id}).count(),Outbox.objects.filter(action_id=a,event__fields__issue_id=${id}).count(),IdempotencyResult.objects.filter(action_id=a,result__data__id=${id}).count()] for a in ['issue.archive','issue.restore']}),default=str))`);
  const failures=[];
  async function test(name,run) {
    if(process.env.WORKPAL_QA_FILTER&&!new RegExp(process.env.WORKPAL_QA_FILTER).test(name)) return;
    const pages=[];
    const open=async viewport=>{const p=await newPage(viewport);p.setDefaultTimeout(6000);pages.push(p);return p;};
    try {await run(open);console.log('PASS '+name);}
    catch(error) {failures.push(name);console.error('FAIL '+name+'\n'+error.message);}
    finally {for(const p of pages)await p.context().close();}
  }
  async function select(p,item,include=false) {
    await signIn(p,base);await p.getByLabel('Workspace',{exact:true}).selectOption('1');
    await p.getByRole('button',{name:'Issues',exact:true}).click();
    if(include)await p.getByLabel('Include archived').check();
    await p.getByLabel('Search issues').fill(item.title);
    await p.getByRole('button',{name:`${item.title} (#${item.id})`,exact:true}).click();
    await expect(p.getByRole('heading',{name:`Requirements version ${item.requirements_revision}`,exact:true})).toBeVisible();
  }
  async function dialog(p,restore=false) {
    const name=restore?'Restore issue':'Archive issue';
    await p.getByRole('button',{name,exact:true}).click();
    return p.getByRole('dialog',{name,exact:true});
  }
  async function submit(d,restore=false) {
    await d.getByRole('button',{name:restore?'Restore issue':'Archive issue',exact:true}).click();
    await expect(d).toHaveCount(0);
  }
  async function edit(p,title) {
    await p.getByRole('button',{name:'Edit requirements',exact:true}).click();
    const d=p.getByRole('dialog');await d.getByLabel('Title',{exact:true}).fill(title);
    await d.getByRole('button',{name:'Save changes',exact:true}).click();await expect(d).toHaveCount(0);
    await expect(p.locator('.issue-detail').getByRole('heading',{name:title,exact:true}).first()).toBeVisible();
  }
  async function hold(p,action) {
    let release,arrived,used=false;
    const gate=new Promise(r=>release=r),ready=new Promise(r=>arrived=r),pattern='**/api/v1/actions/'+action;
    const handler=async route=>{
      if(used)return route.continue();used=true;
      const response=await route.fetch();arrived();await gate;await route.fulfill({response});
    };
    await p.route(pattern,handler);
    return {ready:async()=>{let timer;try{await Promise.race([ready,new Promise((_,reject)=>timer=setTimeout(()=>reject(Error('Held request missing')),6000))]);}finally{clearTimeout(timer);}},
      finish:async()=>{release();await p.waitForLoadState('networkidle');await p.unroute(pattern,handler);}};
  }
  async function loseFirst(p,action) {
    const attempts=[];
    await p.route('**/api/v1/actions/'+action,async route=>{
      attempts.push(route.request().postDataJSON());
      if(attempts.length===1){const response=await route.fetch();assert.equal(response.status(),200);await route.abort('failed');}
      else await route.continue();
    });
    return attempts;
  }
  function preserved(before,after,delta) {
    for(const key of Object.keys(before.issue))if(!['revision','updated_at','archived'].includes(key))assert.deepEqual(after.issue[key],before.issue[key],key);
    assert.equal(after.issue.revision,before.issue.revision+delta);
    assert.deepEqual(after.versions,before.versions);assert.deepEqual(after.notifications,before.notifications);
  }
  function revoke(name) {runPython(`from workpal.access.models import SourceGrant;SourceGrant.objects.filter(user_id=1,source__object_id='archive-${name}').delete()`);}

  await test('Issue read-only denies archive but requirements read-only permits metadata changes',async open=>{
    for(const name of ['issue-readonly','req-readonly']){
      const item=seed[name],p=await open();await select(p,item,true);const before=state(item.id),d=await dialog(p);
      await d.getByRole('button',{name:'Archive issue',exact:true}).click();
      if(name==='issue-readonly'){
        await expect(p.getByRole('button',{name:'Refresh account',exact:true})).toBeVisible();assert.deepEqual(state(item.id),before);
      }else{
        await expect(d).toHaveCount(0);await expect(p.getByRole('button',{name:'Restore issue',exact:true})).toBeVisible();
        await submit(await dialog(p,true),true);await expect(p.getByRole('button',{name:'Archive issue',exact:true})).toBeVisible();
        const after=state(item.id);preserved(before,after,2);assert.deepEqual(after.counts,{'issue.archive':[1,1,1],'issue.restore':[1,1,1]});
      }
    }
  });
  await test('Issue and independent requirements revocation clear content and roll back writes',async open=>{
    for(const name of ['issue-revoke','req-revoke']){
      const item=seed[name],p=await open();await select(p,item);const d=await dialog(p),before=state(item.id);revoke(name);
      const response=p.waitForResponse(r=>r.url().endsWith('/actions/issue.archive'));
      await d.getByRole('button',{name:'Archive issue',exact:true}).click();assert.equal((await response).status(),403);
      await expect(p.getByRole('button',{name:'Refresh account',exact:true})).toBeVisible();await expect(p.locator('.issue-detail')).toHaveCount(0);await expect(d).toHaveCount(0);
      assert.deepEqual(state(item.id),before);
    }
  });
  await test('cached successful archive still checks current requirements access on retry',async open=>{
    const item=seed['replay-revoke'],p=await open();await select(p,item);const d=await dialog(p),attempts=await loseFirst(p,'issue.archive');
    await d.getByRole('button',{name:'Archive issue',exact:true}).click();await expect(d.getByRole('button',{name:'Retry original request',exact:true})).toBeEnabled();
    const before=state(item.id);revoke('replay-revoke');const response=p.waitForResponse(r=>r.url().endsWith('/actions/issue.archive'));
    await d.getByRole('button',{name:'Retry original request',exact:true}).click();assert.equal((await response).status(),403);
    await expect(p.getByRole('button',{name:'Refresh account',exact:true})).toBeVisible();assert.deepEqual(attempts[0],attempts[1]);assert.deepEqual(state(item.id),before);
  });
  for(const restore of [false,true])await test(`lost ${restore?'restore':'archive'} response followed by opposite mutation replays once and reads current state`,async open=>{
    const item=seed[restore?'restore-reverse':'reverse'],a=await open();await select(a,item,true);const before=state(item.id),da=await dialog(a,restore);
    const attempts=await loseFirst(a,restore?'issue.restore':'issue.archive');
    await da.getByRole('button',{name:restore?'Restore issue':'Archive issue',exact:true}).click();await expect(da.getByRole('button',{name:'Retry original request',exact:true})).toBeEnabled();
    const b=await open();await select(b,item,true);await submit(await dialog(b,!restore),!restore);
    await da.getByRole('button',{name:'Retry original request',exact:true}).click();await expect(da).toHaveCount(0);
    await expect(a.getByRole('button',{name:restore?'Restore issue':'Archive issue',exact:true})).toBeVisible();
    await expect(a.locator('.issue-detail').getByText(restore?'Archived':'Active',{exact:true})).toBeVisible();
    const after=state(item.id);preserved(before,after,2);assert.equal(after.issue.archived,restore);
    assert.deepEqual(after.counts,{'issue.archive':[1,1,1],'issue.restore':[1,1,1]});assert.equal(attempts.length,2);assert.deepEqual(attempts[0],attempts[1]);
  });
  await test('closing a pending conflict reload cannot replace the reopened baseline',async open=>{
    const item=seed.reload,a=await open(),b=await open();await select(a,item);await select(b,item);
    const da=await dialog(a);await edit(b,'Remote first');
    await da.getByRole('button',{name:'Archive issue',exact:true}).click();await expect(da.getByRole('button',{name:'Reload current',exact:true})).toBeVisible();
    const held=await hold(a,'issue.read');
    try{
      await da.getByRole('button',{name:'Reload current',exact:true}).click();await held.ready();await a.keyboard.press('Escape');await dialog(a);
      await expect(da.getByRole('button',{name:'Reload current',exact:true})).toBeEnabled();await edit(b,'Remote second');
    }finally{await held.finish();}
    await expect(da.getByText(item.title,{exact:true})).toBeVisible();await expect(da.getByRole('button',{name:'Archive issue',exact:true})).toBeDisabled();
    await da.getByRole('button',{name:'Reload current',exact:true}).click();await expect(da.getByText('Remote second',{exact:true})).toBeVisible();
    const requests=[];a.on('request',r=>{if(r.url().endsWith('/actions/issue.archive'))requests.push(r.postDataJSON());});
    await submit(da);assert.equal(requests[0].expected_revision,3);assert.equal(state(item.id).issue.revision,4);assert.equal(state(item.id).versions.length,3);
  });
  await test('successful conflict reload retains current facts after closing and reopening',async open=>{
    const item=seed.facts,a=await open(),b=await open();await select(a,item);await select(b,item);const da=await dialog(a);await edit(b,'Current reviewed title');
    await da.getByRole('button',{name:'Archive issue',exact:true}).click();await da.getByRole('button',{name:'Reload current',exact:true}).click();
    await expect(da.getByText('Current reviewed title',{exact:true})).toBeVisible();
    await expect(da.getByText('Active',{exact:true})).toBeVisible();await a.keyboard.press('Escape');await dialog(a);
    await expect(da.getByText('Current reviewed title',{exact:true})).toBeVisible();await expect(da.getByText('Active',{exact:true})).toBeVisible();
    await submit(da);assert.equal(state(item.id).issue.revision,3);
  });
  for(const workspace of [false,true])await test(`pending archive cannot change ${workspace?'another workspace':'another Issue'}`,async open=>{
    const item=seed[workspace?'workspace':'other'],p=await open();await select(p,item);const d=await dialog(p),held=await hold(p,'issue.archive');
    try{
      await d.getByRole('button',{name:'Archive issue',exact:true}).click();await held.ready();await p.keyboard.press('Escape');
      if(workspace){await p.getByLabel('Workspace',{exact:true}).selectOption('2');await p.getByRole('button',{name:'Issues',exact:true}).click();await expect(p.getByText('No issues found.',{exact:true})).toBeVisible();}
      else{await p.getByLabel('Search issues').fill(seed.long.title);await p.getByRole('button',{name:`${seed.long.title} (#${seed.long.id})`,exact:true}).click();await expect(p.locator('.issue-detail')).toContainText(seed.long.title);}
    }finally{await held.finish();}
    await expect(p.locator('dialog')).toHaveCount(0);await expect(p.locator('.issue-detail')).not.toContainText(item.title);
  });
  await test('post-archive refresh preserves a newer selection and focus',async open=>{
    const item=seed.refresh,p=await open();await select(p,item,true);const d=await dialog(p),held=await hold(p,'issue.list');
    try{
      await d.getByRole('button',{name:'Archive issue',exact:true}).click();await held.ready();
      await p.getByLabel('Search issues').fill(seed.long.title);const row=p.getByRole('button',{name:`${seed.long.title} (#${seed.long.id})`,exact:true});await row.click();
      await expect(p.locator('.issue-detail')).toContainText(seed.long.title);await expect(row).toBeFocused();
    }finally{await held.finish();}
    await expect(p.locator('.issue-detail')).toContainText(seed.long.title);await expect(p.getByLabel('Search issues')).toHaveValue(seed.long.title);
    await expect(p.getByRole('button',{name:`${seed.long.title} (#${seed.long.id})`,exact:true})).toBeFocused();
  });
  await test('archive filtering uses authorized pages without exposing private requirements',async open=>{
    const item=seed.pages.at(-1),p=await open();await signIn(p,base);await p.getByLabel('Workspace',{exact:true}).selectOption('1');await p.getByRole('button',{name:'Issues',exact:true}).click();
    await p.getByLabel('Search issues').fill('Page archive');await expect(p.locator('.project-row')).toHaveCount(20);
    await p.getByRole('button',{name:'Load more',exact:true}).click();await expect(p.locator('.project-row')).toHaveCount(23);
    assert.deepEqual(await p.locator('.project-row button').allTextContents(),seed.pages.map(i=>`${i.title} (#${i.id})`));
    await p.getByRole('button',{name:`${item.title} (#${item.id})`,exact:true}).click();await submit(await dialog(p));
    await expect(p.getByRole('button',{name:'Refresh issues',exact:true})).toBeFocused();await expect(p.locator('.project-row')).toHaveCount(20);
    await p.getByRole('button',{name:'Load more',exact:true}).click();await expect(p.locator('.project-row')).toHaveCount(22);
    assert.deepEqual(await p.locator('.project-row button').allTextContents(),seed.pages.slice(0,-1).map(i=>`${i.title} (#${i.id})`));
    await p.getByLabel('Include archived').check();await expect(p.locator('.project-row')).toHaveCount(20);await p.getByRole('button',{name:'Load more',exact:true}).click();await expect(p.locator('.project-row')).toHaveCount(23);
    await expect(p.getByRole('button',{name:`${item.title} (#${item.id})`,exact:true}).locator('..')).toContainText('Archived');assert.equal(state(item.id).counts['issue.archive'][0],1);
  });
  await test('long malicious titles fit the dialog and Escape leaves all records unchanged',async open=>{
    const item=seed.long,p=await open({width:390,height:900});await select(p,item);const before=state(item.id),d=await dialog(p);
    await expect(d.getByText(item.title,{exact:true})).toBeVisible();assert(await d.evaluate(node=>node.scrollWidth<=node.clientWidth));assert.equal(await d.locator('img,script').count(),0);
    await p.keyboard.press('Escape');await expect(p.getByRole('button',{name:'Archive issue',exact:true})).toBeFocused();assert.deepEqual(state(item.id),before);
  });
  assert.deepEqual(failures,[],'archive review');
});
