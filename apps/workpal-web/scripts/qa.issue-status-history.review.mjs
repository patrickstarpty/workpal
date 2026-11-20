import assert from 'node:assert/strict';
import {withBrowser,signIn} from './browser-fixture.mjs';

await withBrowser(async({base,newPage,runPython,expect})=>{
  const parse=code=>JSON.parse(runPython(code).trim().split('\n').at(-1));
  const seed=parse(`import json
from django.contrib.auth import get_user_model
from workpal.identity.models import Membership
from workpal.contracts import Actor,ObjectRef
from workpal.work import issues,service,transitions
from workpal.work.models import Issue,IssueTransition
from workpal.access.models import RegisteredObject,SourceGrant
from workpal.access.service import register_object
a=Actor(1,1);p=service.create(a,'History supervision');data={}
for name in ['pages','history-revoke','issue-revoke','other','legacy','missing']:
    i=issues.create(a,p['id'],'Timeline '+name)
    events=[]
    for n in range(28 if name=='pages' else 0 if name=='other' else 3):
        i=transitions.transition(a,i['id'],'todo' if n%2==0 else 'blocked',i['revision'],reason=name+' reason '+str(n),blocked_owner_user_id=2 if n%2 else 0)
    events=transitions.list_transitions(a,i['id'],limit=100)['items']
    data[name]={'issue':i,'events':events}
for index in [0,10,27]:
    ref=register_object(1,ObjectRef('source','timeline-private-'+str(index)),is_source=True)
    register_object(1,transitions.ref(data['pages']['events'][index]['id']),[ref])
for name in ['history-revoke','issue-revoke']:
    ref=register_object(1,ObjectRef('source','timeline-'+name),is_source=True)
    refs=[transitions.ref(e['id']) for e in data[name]['events']] if name=='history-revoke' else [issues.ref(data[name]['issue']['id'])]
    for target in refs:register_object(1,target,[ref])
    SourceGrant.objects.create(user_id=1,source=RegisteredObject.objects.get(kind=ref.kind,object_id=ref.id),read=True,write=True)
# A deliberate legacy-data fixture tests SHA mismatch fallback; normal workflow
# mutation Interfaces do not rewrite an Issue's pinned workflow snapshot.
row=Issue.objects.get(pk=data['legacy']['issue']['id']);snapshot=dict(row.workflow_snapshot);snapshot['sha256']='f'*64
row.workflow_snapshot=snapshot;row.save(update_fields=['workflow_snapshot'])
author=get_user_model().objects.create_user(username='Former author');Membership.objects.create(user=author,workspace_id=1,role='member')
i=data['missing']['issue'];i=transitions.transition(Actor(author.pk,1),i['id'],'blocked',i['revision'],reason='Former owner',blocked_owner_user_id=author.pk)
data['missing']['issue']=i;data['missing']['events']=transitions.list_transitions(a,i['id'])['items'];data['former_id']=author.pk
Membership.objects.filter(user=author,workspace_id=1).delete()
print(json.dumps(data))`);
  const facts=()=>runPython(`import json
from django.db import connection
with connection.cursor() as c:
    tables=[t for t in connection.introspection.table_names() if any(x in t.lower() for x in ['issue','notification','outbox','idempotency','confirmation'])]
    result={}
    for t in tables:
        c.execute('SELECT * FROM "'+t+'" ORDER BY 1');result[t]=c.fetchall()
    print(json.dumps(result,default=str,sort_keys=True))`).trim().split('\n').at(-1);
  const before=facts(),failures=[];
  async function test(name,run){
    if(process.env.WORKPAL_QA_FILTER&&!new RegExp(process.env.WORKPAL_QA_FILTER).test(name))return;
    const pages=[],open=async()=>{const p=await newPage();p.setDefaultTimeout(6000);pages.push(p);return p;};
    try{await run(open);console.log('PASS '+name);}catch(e){failures.push(name);console.error('FAIL '+name+'\n'+e.message);}
    finally{for(const p of pages)await p.context().close();}
  }
  const panel=p=>p.getByRole('region',{name:'Status history',exact:true});
  async function select(p,name){
    await signIn(p,base);await p.getByLabel('Workspace',{exact:true}).selectOption('1');await p.getByRole('button',{name:'Issues',exact:true}).click();
    await choose(p,name);
  }
  async function choose(p,name){
    const item=seed[name].issue;await p.getByLabel('Search issues').fill(item.title);await p.getByRole('button',{name:`${item.title} (#${item.id})`,exact:true}).click();
    await expect(p.getByRole('heading',{name:'Requirements version 1',exact:true})).toBeVisible();await p.waitForLoadState('networkidle');
  }
  async function show(p,count=20){const h=panel(p);await h.getByRole('button',{name:'Show status history',exact:true}).click();await expect(h.locator('details')).toHaveCount(count);return h;}
  async function hold(p,action,match=()=>true){
    let release,arrived,used=false;const gate=new Promise(r=>release=r),ready=new Promise(r=>arrived=r),pattern='**/api/v1/actions/'+action;
    const fn=async route=>{if(used||!match(route.request().postDataJSON()))return route.continue();used=true;const response=await route.fetch();arrived();await gate;await route.fulfill({response});};
    await p.route(pattern,fn);return {ready:async()=>{let timer;try{await Promise.race([ready,new Promise((_,reject)=>timer=setTimeout(()=>reject(Error('Held request missing')),6000))]);}finally{clearTimeout(timer);}},finish:async()=>{release();await p.waitForLoadState('networkidle');await p.unroute(pattern,fn);}};
  }
  const visible=seed.pages.events.filter((_,n)=>![0,10,27].includes(n));
  function summaries(events){return events.map(e=>`${e.from_key==='todo'?'Todo':e.from_key[0].toUpperCase()+e.from_key.slice(1)} → ${e.to_key==='todo'?'Todo':e.to_key[0].toUpperCase()+e.to_key.slice(1)} · ${e.created_at}`);}

  await test('history is lazy and private events are removed before paging without duplicate rows',async open=>{
    const p=await open();await select(p,'pages');const requests=[];p.on('request',r=>{if(/\/actions\/(workspace.people.read|issue.transitions.list)$/.test(r.url()))requests.push(r.url());});
    const h=panel(p);await expect(h.getByRole('button',{name:'Show status history',exact:true})).toHaveAttribute('aria-expanded','false');assert.equal(requests.length,0);
    await show(p);assert.equal(requests.filter(url=>url.endsWith('workspace.people.read')).length,0);
    await expect(h.locator('summary')).toHaveText(summaries(visible.slice(0,20)));
    await h.locator('summary').first().click();await expect(h.locator('details').first()).toContainText('Changed by: owner (#1)');
    await h.getByRole('button',{name:'Load more status history',exact:true}).click();await expect(h.locator('details')).toHaveCount(25);await expect(h.locator('summary')).toHaveText(summaries(visible));
    await expect(h.locator('details').first()).toContainText('Changed by: owner (#1)');
    for(const index of [0,10,27])await expect(h).not.toContainText(seed.pages.events[index].reason);
    assert.deepEqual(facts(),before);
  });
  await test('unblocking history explicitly records that the blocked owner becomes Unassigned',async open=>{
    const p=await open();await select(p,'pages');const h=await show(p);
    // The first visible record enters Blocked; the second leaves it.
    await h.locator('summary').nth(1).click();const row=h.locator('details').nth(1);
    await expect(row).toContainText('Before blocked owner: reader (#2)');
    await expect(row).toContainText('After blocked owner: Unassigned');
    await expect(row).toContainText('Previous blocking reason: pages reason 1');
  });
  await test('refresh removes revoked historical events without falling back to the previous rows',async open=>{
    const p=await open();await select(p,'history-revoke');const h=await show(p,3);await h.locator('summary').first().click();await expect(h).toContainText('history-revoke reason 0');
    runPython("from workpal.access.models import SourceGrant;SourceGrant.objects.filter(user_id=1,source__object_id='timeline-history-revoke').delete()");
    await h.getByRole('button',{name:'Refresh status history',exact:true}).click();await expect(h.locator('details')).toHaveCount(0);await expect(h).toContainText('No status changes.');await expect(h).not.toContainText('history-revoke reason 0');
    await expect(p.locator('.issue-detail')).toContainText(seed['history-revoke'].issue.title);
  });
  await test('Issue source revocation clears the full detail on a history reread',async open=>{
    const p=await open();await select(p,'issue-revoke');const h=await show(p,3);
    runPython("from workpal.access.models import SourceGrant;SourceGrant.objects.filter(user_id=1,source__object_id='timeline-issue-revoke').delete()");
    await h.getByRole('button',{name:'Refresh status history',exact:true}).click();await expect(p.getByRole('button',{name:'Refresh account',exact:true})).toBeVisible();await expect(p.locator('.issue-detail')).toHaveCount(0);
  });
  await test('page failure retains authorized rows and retry appends the page exactly once',async open=>{
    const p=await open();await select(p,'pages');const h=await show(p);let failed=false;const cursors=[];
    await p.route('**/api/v1/actions/issue.transitions.list',async route=>{const body=route.request().postDataJSON();cursors.push(body.payload.cursor);if(!failed&&body.payload.cursor){failed=true;return route.abort('failed');}await route.continue();});
    await h.getByRole('button',{name:'Load more status history',exact:true}).click();await expect(h.getByRole('button',{name:'Retry',exact:true})).toBeVisible();await expect(h.locator('details')).toHaveCount(20);await expect(h).not.toContainText('No status changes.');
    await h.getByRole('button',{name:'Retry',exact:true}).click();await expect(h.locator('summary')).toHaveText(summaries(visible));assert.equal(cursors.length,2);assert.equal(cursors[0],cursors[1]);
    failed=false;await h.getByRole('button',{name:'Refresh status history',exact:true}).click();await expect(h.locator('summary')).toHaveText(summaries(visible.slice(0,20)));assert.equal(cursors.at(-1),0);
  });
  await test('hiding and reopening ignores the response from the earlier expansion',async open=>{
    const p=await open();await select(p,'pages');const h=panel(p),held=await hold(p,'issue.transitions.list');
    try{await h.getByRole('button',{name:'Show status history',exact:true}).click();await held.ready();await h.getByRole('button',{name:'Hide status history',exact:true}).click();await expect(h.locator('details')).toHaveCount(0);await show(p);}finally{await held.finish();}
    await expect(h.locator('summary')).toHaveText(summaries(visible.slice(0,20)));await expect(h.getByRole('button',{name:'Load more status history',exact:true})).toBeEnabled();
  });
  await test('refresh invalidates an in-flight next page while keeping the new first page',async open=>{
    const p=await open();await select(p,'pages');const h=await show(p),held=await hold(p,'issue.transitions.list',r=>r.payload.cursor>0);
    try{await h.getByRole('button',{name:'Load more status history',exact:true}).click();await held.ready();await h.getByRole('button',{name:'Refresh status history',exact:true}).click();await expect(h.locator('summary')).toHaveText(summaries(visible.slice(0,20)));}finally{await held.finish();}
    await expect(h.locator('details')).toHaveCount(20);await h.getByRole('button',{name:'Load more status history',exact:true}).click();await expect(h.locator('summary')).toHaveText(summaries(visible));
  });
  await test('late person lookup from hidden history does not repaint the replacement rows',async open=>{
    const p=await open();await select(p,'pages');const h=await show(p),held=await hold(p,'workspace.people.read',r=>r.payload.user_id===1);
    try{await h.locator('summary').first().click();await held.ready();await h.getByRole('button',{name:'Hide status history',exact:true}).click();await show(p);}finally{await held.finish();}
    await expect(h.locator('details[open]')).toHaveCount(0);await expect(h).not.toContainText('Changed by');await h.locator('summary').first().click();await expect(h.locator('details').first()).toContainText('Changed by: owner (#1)');
  });
  for(const workspace of [false,true])await test(`late history cannot appear after switching ${workspace?'workspace':'Issue'}`,async open=>{
    const p=await open();await select(p,'pages');const held=await hold(p,'issue.transitions.list');
    try{await panel(p).getByRole('button',{name:'Show status history',exact:true}).click();await held.ready();
      if(workspace){await p.getByLabel('Workspace',{exact:true}).selectOption('2');await p.getByRole('button',{name:'Issues',exact:true}).click();await expect(p.getByText('No issues found.',{exact:true})).toBeVisible();}
      else{await choose(p,'other');await show(p,0);await expect(panel(p)).toContainText('No status changes.');}
    }finally{await held.finish();}
    await expect(p.locator('main')).not.toContainText('pages reason');await expect(p.locator('.issue-status-history details')).toHaveCount(0);
  });
  await test('legacy workflow mismatch preserves raw historical keys and former people remain unavailable',async open=>{
    const p=await open();await select(p,'legacy');let h=await show(p,3);await expect(h.locator('summary').first()).toHaveText(`backlog → todo · ${seed.legacy.events[0].created_at}`);
    await choose(p,'missing');await expect(p.locator('.issue-detail')).toContainText(`Blocked owner: Unavailable person (#${seed.former_id})`);
    h=await show(p,4);await h.locator('summary').last().click();await expect(h.locator('details').last()).toContainText(`Changed by: Unavailable person (#${seed.former_id})`);await expect(h.locator('details').last()).not.toContainText('Former author');
  });
  await test('a historical person label can retry locally without losing the event or other rows',async open=>{
    const p=await open();await select(p,'pages');const h=await show(p);let failed=false;
    await p.route('**/api/v1/actions/workspace.people.read',async route=>{if(!failed&&route.request().postDataJSON().payload.user_id===1){failed=true;return route.abort('failed');}await route.continue();});
    await h.locator('summary').first().click();const row=h.locator('details').first();await row.getByRole('button',{name:'Retry',exact:true}).click();await expect(row).toContainText('Changed by: owner (#1)');await expect(h.locator('details')).toHaveCount(20);
  });
  assert.deepEqual(facts(),before,'all history browser checks are read-only');
  assert.deepEqual(failures,[],'status history review');
});
