import assert from 'node:assert/strict';
import path from 'node:path';
import {withBrowser, signIn} from './browser-fixture.mjs';

await withBrowser(async ({base, newPage, runPython, repo, expect}) => {
  const seed = JSON.parse(runPython(`
import json
from workpal.work import service
from workpal.contracts import Actor, ObjectRef
from workpal.access.service import register_object
from workpal.access.models import SourceGrant, RegisteredObject
a=Actor(1,1)
hidden=register_object(1,ObjectRef('source','qa-hidden'),is_source=True)
gate=register_object(1,ObjectRef('source','qa-revocable'),is_source=True)
data={}
for i in range(25):
    if i in (0,10,24):
        p=service.create(a,'Page secret '+str(i))
        register_object(1,service.ref(p['id']),[hidden])
    service.create(a,'Page '+str(i).zfill(2))
for key,name,description in [('first','Duplicate','First distinct project'),('second','Duplicate','Second distinct project'),('conflict','Conflict','Conflict check'),('race','Refresh race','Refresh check'),('revocable','Revocable','Private project')]:
    data[key]=service.create(a,name,description)
register_object(1,service.ref(data['revocable']['id']),[gate])
SourceGrant.objects.create(user_id=1,source=RegisteredObject.objects.get(kind=gate.kind,object_id=gate.id),read=True,write=True)
data['other']=service.create(Actor(1,2),'Other workspace')
print(json.dumps(data))
`).trim().split('\n').at(-1));
  const failures = [];
  async function test(name, run) {
    const pages = [];
    const open = async viewport => { const p = await newPage(viewport); pages.push(p); return p; };
    try { await run(open); console.log('PASS ' + name); }
    catch (e) { failures.push(name); console.error('FAIL ' + name + '\n' + e.message); }
    finally { for (const p of pages) await p.context().close(); }
  }
  async function projects(p, username='owner', ws='1') {
    await signIn(p, base, username);
    await p.getByLabel('Workspace', {exact:true}).selectOption(ws);
    await p.getByRole('button', {name:'Projects', exact:true}).click();
    await p.getByRole('heading', {name:'Projects', exact:true}).waitFor();
  }
  async function search(p, value) {
    await p.getByLabel('Search projects').fill(value);
    await p.waitForLoadState('networkidle');
  }
  async function detail(p, item) {
    await search(p, item.name);
    await p.getByRole('button', {name:item.name + ' (#' + item.id + ')', exact:true}).click();
    await expect(p.getByRole('heading', {name:item.name, exact:true})).toBeVisible();
  }
  async function hold(p, pattern, match) {
    let release, arrived;
    const held = new Promise(resolve => { release = resolve; });
    const ready = new Promise(resolve => { arrived = resolve; });
    let used = false;
    const handler = async route => {
      if (!used && match(route.request())) {
        used = true; const response = await route.fetch(); arrived(); await held;
        await route.fulfill({response});
      } else await route.continue();
    };
    await p.route(pattern, handler);
    return {ready:() => Promise.race([ready, new Promise((_,reject) => {const t=setTimeout(()=>reject(Error('Expected request did not arrive')),5000);t.unref();})]),
      finish:async () => {release(); await p.waitForLoadState('networkidle'); await p.unroute(pattern,handler);}};
  }
  await test('authorized pagination, search reset, duplicate names and workspace isolation', async open => {
    const p = await open(); await projects(p); await search(p,'Page');
    await expect(p.locator('.project-row')).toHaveCount(20);
    await expect(p.locator('.project-row')).not.toContainText(['secret']);
    await p.getByRole('button', {name:'Load more', exact:true}).click();
    await expect(p.locator('.project-row')).toHaveCount(25);
    const rows = await p.locator('.project-row button').allTextContents();
    assert.equal(new Set(rows).size,25); assert(rows.every(s=>!s.includes('secret')));
    await expect(p.getByRole('button', {name:'Load more', exact:true})).toBeHidden();
    await search(p,'Page 24'); await expect(p.locator('.project-row')).toHaveCount(1);
    await detail(p,seed.second); await expect(p.locator('section section')).toContainText(seed.second.description);
    await p.getByLabel('Workspace', {exact:true}).selectOption('2');
    await p.getByRole('button', {name:'Projects', exact:true}).click();
    await expect(p.locator('.project-row')).toHaveCount(1);
    await expect(p.locator('.project-row')).toContainText(['Other workspace']);
  });
  await test('member sees permitted project facts and no management controls', async open => {
    const p = await open(); await projects(p,'reader'); await detail(p,seed.first);
    for (const name of ['Create project','Edit project','Archive project','Restore project']) await expect(p.getByRole('button',{name,exact:true})).toHaveCount(0);
    await search(p,'Revocable'); await expect(p.getByText('No projects found.',{exact:true})).toBeVisible();
    await expect(p.getByLabel('Workspace',{exact:true}).locator('option')).toHaveCount(2);
  });
  await test('source grant revocation clears an open editor and prevents the write', async open => {
    const p=await open(); await projects(p); await detail(p,seed.revocable);
    await p.getByRole('button',{name:'Edit project',exact:true}).click();
    await p.getByLabel('Project name').fill('Forbidden change');
    runPython("from workpal.access.models import SourceGrant; SourceGrant.objects.filter(source__object_id='qa-revocable',user_id=1).delete()");
    await p.getByRole('button',{name:'Save',exact:true}).click();
    await expect(p.getByRole('button',{name:'Refresh account'})).toBeVisible();
    await expect(p.locator('dialog')).toHaveCount(0); await expect(p.locator('.project-row')).toHaveCount(0);
    runPython(`from workpal.work.models import Project; assert Project.objects.get(pk=${seed.revocable.id}).name == 'Revocable'`);
    await p.getByRole('button',{name:'Refresh account'}).click();
    await p.getByLabel('Workspace',{exact:true}).selectOption('1'); await p.getByRole('button',{name:'Projects',exact:true}).click();
    await search(p,'Revocable'); await expect(p.getByText('No projects found.',{exact:true})).toBeVisible();
  });
  await test('create response loss followed by refresh retains one intent and one record', async open => {
    const p=await open(); await projects(p); const requests=[];
    await p.route('**/api/v1/actions/project.create',async route=>{
      requests.push(route.request().postDataJSON());
      if(requests.length===1){const response=await route.fetch();assert.equal(response.status(),200);await route.abort('failed');}else await route.continue();
    });
    await p.getByRole('button',{name:'Create project'}).click();
    await p.getByLabel('Project name').fill('Create response lost');
    await p.getByLabel('Description',{exact:true}).fill('One user intent');
    await p.getByRole('button',{name:'Save',exact:true}).click();
    await expect(p.getByRole('button',{name:'Retry original request'})).toBeVisible();
    await p.getByRole('button',{name:'Reload project'}).click(); await p.waitForLoadState('networkidle');
    await p.locator('dialog button[type=submit]').click(); await expect(p.locator('dialog')).toHaveCount(0);
    const counts=JSON.parse(runPython("import json; from workpal.work.models import Project; from workpal.audit.models import AuditEvent,Outbox; from workpal.actions.models import IdempotencyResult; print(json.dumps([Project.objects.filter(name='Create response lost').count(),AuditEvent.objects.filter(action_id='project.create',fields__name='Create response lost').count(),Outbox.objects.filter(action_id='project.create',event__fields__name='Create response lost').count(),IdempotencyResult.objects.filter(action_id='project.create').count()]))").trim().split('\n').at(-1));
    assert.deepEqual({requests:requests.length,same:JSON.stringify(requests[0])===JSON.stringify(requests[1]),counts},{requests:2,same:true,counts:[1,1,1,1]});
    const fresh=await open(); await projects(fresh); await search(fresh,'Create response lost'); await expect(fresh.locator('.project-row')).toHaveCount(1);
  });
  await test('two editors conflict without losing the draft', async open => {
    const p=await open(),q=await open(); await projects(p); await projects(q); await detail(p,seed.conflict); await detail(q,seed.conflict);
    await p.getByRole('button',{name:'Edit project'}).click(); await p.getByLabel('Project name').fill('Draft survives conflict');
    await q.getByRole('button',{name:'Edit project'}).click(); await q.getByLabel('Project name').fill('Concurrent project');
    await q.getByRole('button',{name:'Save',exact:true}).click(); await expect(q.locator('dialog')).toHaveCount(0);
    await p.getByRole('button',{name:'Save',exact:true}).click(); await expect(p.getByRole('alert')).toContainText('project changed');
    await expect(p.getByLabel('Project name')).toHaveValue('Draft survives conflict');
    await p.getByRole('button',{name:'Reload project'}).click(); await expect(p.getByRole('heading',{name:'Concurrent project',exact:true})).toBeVisible();
    await expect(p.getByLabel('Project name')).toHaveValue('Draft survives conflict');
    await p.getByRole('button',{name:'Save',exact:true}).click(); await expect(p.locator('dialog')).toHaveCount(0);
    await expect(p.getByRole('heading',{name:'Draft survives conflict',exact:true})).toBeVisible();
  });
  await test('project navigation immediately clears the previous page while catalog loads', async open => {
    const p=await open(); await signIn(p,base); await p.getByLabel('Workspace',{exact:true}).selectOption('1');
    await p.getByRole('button',{name:'Edit workspace'}).waitFor();
    const gate=await hold(p,'**/api/v1/actions?*',()=>true);
    try{await p.getByRole('button',{name:'Projects',exact:true}).click();await gate.ready();await expect(p.getByRole('button',{name:'Edit workspace'})).toHaveCount(0);}finally{await gate.finish();}
  });
  await test('late search and detail responses preserve the latest selection', async open => {
    const p=await open(); await projects(p);
    const listGate=await hold(p,'**/api/v1/actions/project.list',r=>r.postDataJSON().payload.query==='Page 00');
    try{await p.getByLabel('Search projects').fill('Page 00');await listGate.ready();await p.getByLabel('Search projects').fill('Page 24');await expect(p.locator('.project-row')).toContainText(['Page 24']);}finally{await listGate.finish();}
    await expect(p.locator('.project-row')).toHaveCount(1);await expect(p.locator('.project-row')).toContainText(['Page 24']);
    await search(p,'Duplicate');const detailGate=await hold(p,'**/api/v1/actions/project.read',r=>r.postDataJSON().payload.project_id===seed.first.id);
    try{await p.getByRole('button',{name:`Duplicate (#${seed.first.id})`,exact:true}).click();await detailGate.ready();await p.getByRole('button',{name:`Duplicate (#${seed.second.id})`,exact:true}).click();await expect(p.locator('section section')).toContainText(seed.second.description);}finally{await detailGate.finish();}
    await expect(p.locator('section section')).toContainText(seed.second.description);
    const workspaceGate=await hold(p,'**/api/v1/actions/project.read',r=>r.postDataJSON().payload.project_id===seed.first.id);
    try{await p.getByRole('button',{name:`Duplicate (#${seed.first.id})`,exact:true}).click();await workspaceGate.ready();await p.getByLabel('Workspace',{exact:true}).selectOption('2');await p.getByRole('button',{name:'Projects',exact:true}).click();await expect(p.locator('.project-row')).toContainText(['Other workspace']);}finally{await workspaceGate.finish();}
    await expect(p.getByRole('heading',{name:'Duplicate',exact:true})).toHaveCount(0);
  });
  await test('a save refresh cannot open its old project after a new selection', async open => {
    const p=await open();await projects(p);await detail(p,seed.race);await p.getByRole('button',{name:'Edit project'}).click();await p.getByLabel('Project name').fill('Saved refresh race');
    const gate=await hold(p,'**/api/v1/actions/project.list',()=>true);
    try{await p.getByRole('button',{name:'Save',exact:true}).click();await gate.ready();await p.getByLabel('Search projects').fill('Duplicate');await p.getByRole('button',{name:`Duplicate (#${seed.second.id})`,exact:true}).click();await expect(p.locator('section section')).toContainText(seed.second.description);}finally{await gate.finish();}
    await expect(p.getByRole('heading',{name:'Duplicate',exact:true})).toBeVisible();
  });
  await test('long malicious content fits the mobile detail and keyboard dialog', async open => {
    const p=await open();await projects(p);await p.getByRole('button',{name:'Create project'}).click();
    const name='N'.repeat(200),description='<img src=x onerror=alert(1)>\n'+'D'.repeat(9900);
    await p.getByLabel('Project name').fill(name);await p.getByLabel('Description',{exact:true}).fill(description);
    await p.getByRole('button',{name:'Save',exact:true}).click();await expect(p.locator('dialog')).toHaveCount(0);await expect(p.getByRole('heading',{name,exact:true})).toBeVisible();
    assert.equal(await p.locator('main img').count(),0);
    await p.setViewportSize({width:390,height:844});assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'long project heading must wrap');
    const edit=p.getByRole('button',{name:'Edit project'});await edit.focus();await p.keyboard.press('Enter');await expect(p.getByLabel('Project name')).toBeFocused();await p.keyboard.press('Tab');await expect(p.getByLabel('Description',{exact:true})).toBeFocused();await p.keyboard.press('Escape');await expect(edit).toBeFocused();
    await p.screenshot({path:path.join(repo,'outputs/workpal-web/a53-projects-long-mobile.png')});
  });
  assert.deepEqual(failures,[],'project browser review failures');
});
