import assert from 'node:assert/strict';
import {withBrowser, signIn} from './browser-fixture.mjs';

await withBrowser(async ({base, newPage, runPython, expect}) => {
  const seed = JSON.parse(runPython(`
import json
from workpal.contracts import Actor,ObjectRef
from workpal.work import service,issues,transitions
from workpal.workflows import service as workflows
from workpal.workflows.contracts import default_definition
from workpal.access.service import register_object
from workpal.access.models import RegisteredObject,SourceGrant
a=Actor(1,1);p=service.create(a,'Issue project');data={}
for name in ('hidden-current','old-history','revoked-issue'):
    register_object(1,ObjectRef('source',name),is_source=True)
for n in range(25):
    if n in (0,10,24):
        h=issues.create(a,p['id'],'Visible private '+str(n))
        register_object(1,issues.requirement_ref(h['requirements_version_id']),[ObjectRef('source','hidden-current')])
    issues.create(a,p['id'],'Visible '+str(n).zfill(2))
for key,name,description in [('first','Same title','First record'),('second','Same title','Second record'),('history','History old','Old text'),('revocable','Revocable old','Restricted issue'),('long','L'*300,'<img src=x onerror=alert(1)>\\n'+'D'*19900)]:
    data[key]=issues.create(a,p['id'],name,description=description,criteria=[{'key':'acceptance','text':'Real criterion'}])
data['history_old']=data['history']
data['history']=issues.update(a,data['history']['id'],1,title='History current',description='Current text',criteria=[{'key':'new','text':'New criterion'}])
data['revocable']=issues.update(a,data['revocable']['id'],1,title='Revocable current')
register_object(1,issues.requirement_ref(data['history_old']['requirements_version_id']),[ObjectRef('source','old-history')])
register_object(1,issues.ref(data['revocable']['id']),[ObjectRef('source','revoked-issue')])
for name in ('old-history','revoked-issue'):
    SourceGrant.objects.create(user_id=1,source=RegisteredObject.objects.get(kind='source',object_id=name),read=True,write=True)
definition=default_definition();definition['states'][0]['label']='Queue at creation'
draft=workflows.create(a,'Original workflow',definition);v=workflows.publish(a,draft['id'],draft['revision'])
p=service.set_workflow(a,p['id'],v['id'],p['revision'])
data['custom']=issues.create(a,p['id'],'Stored workflow')
definition['states'][0]['label']='Replacement queue'
draft=workflows.update(a,draft['id'],workflows.read(a,draft['id'])['revision'],definition=definition)
v2=workflows.publish(a,draft['id'],draft['revision']);service.set_workflow(a,p['id'],v2['id'],p['revision'])
archived=issues.create(a,p['id'],'Archived task');data['archived']=issues.archive(a,archived['id'],1)
progress=issues.create(a,p['id'],'Readable status');progress=transitions.transition(a,progress['id'],'todo',1);data['progress']=transitions.transition(a,progress['id'],'in_progress',2)
other=service.create(Actor(1,2),'Other project');data['other']=issues.create(Actor(1,2),other['id'],'Other workspace task')
print(json.dumps(data))
`).trim().split('\n').at(-1));
  const snapshot = () => runPython("from django.apps import apps; from workpal.audit.models import Outbox; from workpal.actions.models import IdempotencyResult; import json; print(json.dumps({**{m._meta.label:list(m.objects.order_by('pk').values()) for m in apps.get_models() if m._meta.app_label in ('work','workflows')},'outbox':list(Outbox.objects.values()),'cache':list(IdempotencyResult.objects.values())},sort_keys=True,default=str))");
  const before = snapshot(), observed = [], failures = [];
  async function test(name, run) {
    const pages=[];
    const open=async viewport=>{const p=await newPage(viewport);pages.push(p);p.on('request',r=>{if(r.method()==='POST'&&r.url().includes('/api/v1/actions/'))observed.push(r.url().split('/').at(-1));});return p;};
    try{await run(open);console.log('PASS '+name);}catch(e){failures.push(name);console.error('FAIL '+name+'\n'+e.message);}finally{for(const p of pages)await p.context().close();}
  }
  async function enter(p,username='owner') {
    await signIn(p,base,username);await p.getByLabel('Workspace',{exact:true}).selectOption('1');await p.getByRole('button',{name:'Issues',exact:true}).click();await p.getByRole('heading',{name:'Issues',exact:true}).waitFor();
  }
  async function search(p,value){await p.getByLabel('Search issues').fill(value);await p.waitForLoadState('networkidle');}
  async function choose(p,item){await search(p,item.title);await p.getByRole('button',{name:`${item.title} (#${item.id})`,exact:true}).click();await expect(p.getByRole('heading',{name:`Requirements version ${item.requirements_revision}`,exact:true})).toBeVisible();}
  async function hold(p,pattern,match){
    let release,arrived,used=false;const held=new Promise(r=>release=r),ready=new Promise(r=>arrived=r);
    const handler=async route=>{if(!used&&match(route.request())){used=true;const response=await route.fetch();assert.equal(response.status(),200);arrived();await held;await route.fulfill({response});}else await route.continue();};await p.route(pattern,handler);
    return {ready:()=>Promise.race([ready,new Promise((_,reject)=>{const t=setTimeout(()=>reject(Error('Expected request missing')),5000);t.unref();})]),finish:async()=>{release();await p.waitForLoadState('networkidle');await p.unroute(pattern,handler);}};
  }
  await test('private current versions are excluded before paging; duplicate titles select exact records',async open=>{
    const p=await open();await enter(p);await search(p,'Visible');await expect(p.locator('.project-row')).toHaveCount(20);await p.getByRole('button',{name:'Load more',exact:true}).click();await expect(p.locator('.project-row')).toHaveCount(25);
    const names=await p.locator('.project-row button').allTextContents();assert.equal(new Set(names).size,25);assert(names.every(n=>!n.includes('private')));await expect(p.getByRole('button',{name:'Load more',exact:true})).toBeHidden();
    await search(p,'Visible 24');await expect(p.locator('.project-row')).toHaveCount(1);await choose(p,seed.second);await expect(p.locator('.issue-detail>p').first()).toHaveText('Second record');
    await search(p,'Archived task');await expect(p.getByText('No issues found.',{exact:true})).toBeVisible();await p.getByLabel('Include archived').check();await expect(p.locator('.project-row')).toHaveCount(1);await expect(p.locator('.project-row')).toContainText(['Archived']);
    const member=await open();await enter(member,'reader');await choose(member,seed.first);await expect(member.getByRole('button',{name:'Previous version'})).toBeDisabled();await expect(member.getByRole('button',{name:'Next version'})).toBeDisabled();
  });
  await test('independent historical revocation clears all rendered content without fallback',async open=>{
    const p=await open();await enter(p);await choose(p,seed.history);await p.getByRole('button',{name:'Previous version'}).click();await expect(p.locator('.issue-history')).toContainText('Old text');
    await p.getByRole('button',{name:'Next version'}).click();await expect(p.locator('.issue-history')).toContainText('Current text');
    runPython("from workpal.access.models import SourceGrant; SourceGrant.objects.filter(source__object_id='old-history').delete()");
    await p.getByRole('button',{name:'Previous version'}).click();await expect(p.getByRole('button',{name:'Refresh account'})).toBeVisible();await expect(p.locator('.issue-detail')).toHaveCount(0);await expect(p.getByText('Old text',{exact:true})).toHaveCount(0);await expect(p.getByText('Current text',{exact:true})).toHaveCount(0);
  });
  await test('Issue source revocation rejects the next history read and removes old facts',async open=>{
    const p=await open();await enter(p);await choose(p,seed.revocable);runPython("from workpal.access.models import SourceGrant; SourceGrant.objects.filter(source__object_id='revoked-issue').delete()");
    await p.getByRole('button',{name:'Previous version'}).click();await expect(p.getByRole('button',{name:'Refresh account'})).toBeVisible();await expect(p.locator('.project-row')).toHaveCount(0);await expect(p.locator('.issue-detail')).toHaveCount(0);
  });
  await test('Issue retains its saved custom workflow label after project rebinding',async open=>{
    const p=await open();await enter(p);await choose(p,seed.custom);await expect(p.getByText('Status: Queue at creation',{exact:true})).toBeVisible();await expect(p.getByText('Status: Replacement queue',{exact:true})).toHaveCount(0);
  });
  await test('late list and detail reads cannot replace newer choices',async open=>{
    const p=await open();await enter(p);const list=await hold(p,'**/api/v1/actions/issue.list',r=>r.postDataJSON().payload.query==='Visible 00');
    try{await p.getByLabel('Search issues').fill('Visible 00');await list.ready();await p.getByLabel('Search issues').fill('Visible 24');await expect(p.locator('.project-row')).toContainText(['Visible 24']);}finally{await list.finish();}
    await expect(p.locator('.project-row')).toHaveCount(1);await expect(p.locator('.project-row')).toContainText(['Visible 24']);await search(p,'Same title');
    const detail=await hold(p,'**/api/v1/actions/issue.read',r=>r.postDataJSON().payload.issue_id===seed.first.id);
    try{await p.getByRole('button',{name:`Same title (#${seed.first.id})`,exact:true}).click();await detail.ready();await p.getByRole('button',{name:`Same title (#${seed.second.id})`,exact:true}).click();await expect(p.locator('.issue-history')).toContainText('Second record');}finally{await detail.finish();}
    await expect(p.locator('.issue-history')).toContainText('Second record');
  });
  await test('late historical version cannot replace another Issue or workspace',async open=>{
    runPython("from workpal.access.models import SourceGrant,RegisteredObject; SourceGrant.objects.update_or_create(user_id=1,source=RegisteredObject.objects.get(kind='source',object_id='old-history'),defaults=dict(read=True,write=True))");
    const p=await open();await enter(p);await choose(p,seed.history);
    const history=await hold(p,'**/api/v1/actions/issue.requirements.read',r=>r.postDataJSON().payload.number===1);
    try{await p.getByRole('button',{name:'Previous version'}).click();await history.ready();await search(p,'Same title');await choose(p,seed.second);}finally{await history.finish();}
    await expect(p.locator('.issue-history')).toContainText('Second record');await expect(p.getByText('Old text',{exact:true})).toHaveCount(0);
    await choose(p,seed.history);const workspace=await hold(p,'**/api/v1/actions/issue.requirements.read',r=>r.postDataJSON().payload.number===1);
    try{await p.getByRole('button',{name:'Previous version'}).click();await workspace.ready();await p.getByLabel('Workspace',{exact:true}).selectOption('2');await p.getByRole('button',{name:'Issues',exact:true}).click();await expect(p.locator('.project-row')).toContainText(['Other workspace task']);}finally{await workspace.finish();}
    await expect(p.locator('.issue-history')).toHaveCount(0);await expect(p.getByText('Old text',{exact:true})).toHaveCount(0);
  });
  await test('list statuses use readable English labels',async open=>{
    const p=await open();await enter(p);await search(p,'Readable status');await expect(p.locator('.project-row')).toContainText(['In progress']);
  });
  await test('maximum title and description render as text at 390px',async open=>{
    const p=await open({width:390,height:844});await enter(p);await choose(p,seed.long);assert.equal(await p.locator('main img').count(),0);assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await expect(p.locator('.issue-history')).toContainText('<img src=x onerror=alert(1)>');
  });
  assert.equal(snapshot(),before,'read journeys must not change business entities, outbox or idempotency cache');
  assert(observed.every(a=>['workspace.read','project.read','issue.read','issue.list','issue.requirements.read'].includes(a)),'only read actions were sent');
  runPython("from workpal.audit.models import AuditEvent; events=AuditEvent.objects.filter(action_id='issue.requirements.read'); assert events.exists(); assert all(any(r['kind']=='issue_requirements' for r in e.scope_refs) for e in events)");
  assert.deepEqual(failures,[],'Issue browser review failures');
});
