import {withBrowser,signIn} from './browser-fixture.mjs';
await withBrowser(async({base,newPage,runPython,expect})=>{
 const i=JSON.parse(runPython(`import json
from workpal.contracts import Actor,ObjectRef
from workpal.work import service,issues
from workpal.access.service import register_object
from workpal.access.models import SourceGrant,RegisteredObject
a=Actor(1,1);p=service.create(a,'Hierarchy review');i=issues.create(a,p['id'],'Hierarchy restricted root');s=ObjectRef('source','hierarchy-review');register_object(1,s,is_source=True);register_object(1,issues.ref(i['id']),[s]);row=RegisteredObject.objects.get(kind=s.kind,object_id=s.id)
for uid in [1,2]:SourceGrant.objects.create(user_id=uid,source=row,read=True,write=True)
print(json.dumps(i))`).trim().split('\n').at(-1));
 const p=await newPage();await signIn(p,base,'reader');await p.getByLabel('Workspace',{exact:true}).selectOption('1');await p.getByRole('button',{name:'Issues',exact:true}).click();await p.getByLabel('Search issues').fill(i.title);await p.getByRole('button',{name:`${i.title} (#${i.id})`,exact:true}).click();const s=p.getByRole('region',{name:'Issue hierarchy'});await s.getByRole('button',{name:'Show hierarchy',exact:true}).focus();await p.keyboard.press('Enter');await expect(s.getByRole('button',{name:'Refresh hierarchy',exact:true})).toBeFocused();await expect(s).toContainText('No visible subtasks.');runPython(`from workpal.access.models import SourceGrant;SourceGrant.objects.filter(user_id=2,source__object_id='hierarchy-review').update(read=False,write=False)`);await s.getByRole('button',{name:'Refresh hierarchy',exact:true}).click();await expect(s).toHaveCount(0);console.log('PASS hierarchy_read_revocation: real permission loss clears current detail');
});

// Snapshot every installed business model, including through models. Fixture writes
// happen outside each measured interval; UUID audit keys cannot use prefix checks.
const decode = output => JSON.parse(output.trim().split('\n').at(-1));
const snapshot = runPython => decode(runPython(`import json,datetime,decimal,uuid
from django.apps import apps
def stable(v):
 if isinstance(v,(bytes,memoryview)):return bytes(v).hex()
 if isinstance(v,(datetime.date,datetime.datetime,datetime.time)):return v.isoformat()
 return str(v)
result={}
for model in apps.get_models(include_auto_created=True):
 if model._meta.app_config.name.startswith('workpal.'):
  result[model._meta.label]=list(model.objects.order_by('pk').values())
print(json.dumps(result,default=stable,sort_keys=True))`));
import assert from 'node:assert/strict';
function unchanged(before,after){
 for(const [table,rows] of Object.entries(before)){
  if(table.endsWith('.AuditEvent')){
   const old=new Map(rows.map(r=>[r.id,r]));
   for(const row of rows)assert.deepEqual(after[table].find(r=>r.id===row.id),row);
   for(const row of after[table].filter(r=>!old.has(r.id)))assert(['issue.requirements.read','issue.read','issue.children.list','issue.list','action.catalog','project.list','project.read','issue.dependencies.list'].includes(row.action_id),JSON.stringify(row));
  }else assert.deepEqual(after[table],rows,table);
 }
}
const fixture = `import json
from workpal.contracts import Actor,ObjectRef
from workpal.work import service,issues
from workpal.access.service import register_object
from workpal.access.models import RegisteredObject,SourceGrant
a=Actor(1,1);p=service.create(a,'R1 parent project');q=service.create(a,'R1 child project');root=issues.create(a,p['id'],'R1 root')
def restrict(ref,key,member=True):
 s=ObjectRef('source',key);register_object(1,s,is_source=True);register_object(1,ref,[s]);row=RegisteredObject.objects.get(kind=s.kind,object_id=s.id)
 for uid in ([1,2] if member else [1]):SourceGrant.objects.create(user_id=uid,source=row,read=True,write=True)
restrict(issues.ref(root['id']),'r1-root')
children=[issues.create(a,q['id'],f'R1 child {n:02d}',parent_issue_id=root['id']) for n in range(22)]
restrict(issues.requirement_ref(children[0]['requirements_version_id']),'r1-child-requirement')
private=issues.create(a,q['id'],'SECRET private child',parent_issue_id=root['id']);restrict(issues.ref(private['id']),'r1-private',False)
hidden=issues.create(a,q['id'],'SECRET requirement child',parent_issue_id=root['id']);restrict(issues.requirement_ref(hidden['requirements_version_id']),'r1-hidden-requirement',False)
archived=issues.create(a,q['id'],'R1 archived child',parent_issue_id=root['id']);issues.archive(a,archived['id'],archived['revision'])
print(json.dumps(dict(root=root,children=children,archived=archived)))`;
async function openRoot(p,base,i){await signIn(p,base,'reader');await p.getByLabel('Workspace',{exact:true}).selectOption('1');await p.getByRole('button',{name:'Issues',exact:true}).click();await p.getByLabel('Search issues').fill(i.title);await p.getByRole('button',{name:`${i.title} (#${i.id})`,exact:true}).click();}
for(const permissions of [false,true])await withBrowser(async({base,newPage,runPython,expect})=>{
 const data=decode(runPython(fixture)),p=await newPage();await openRoot(p,base,data.root);
 const pages=[];p.on('response',async response=>{if(response.url().endsWith('/actions/issue.children.list')&&response.ok())pages.push(await response.json());});
 const s=p.getByRole('region',{name:'Issue hierarchy'});
 const measure=async fn=>{const before=snapshot(runPython);await fn();unchanged(before,snapshot(runPython));};
 await measure(async()=>{
 await s.getByRole('button',{name:'Show hierarchy',exact:true}).click();await expect(s.locator('.project-row')).toHaveCount(20);
 await s.getByRole('button',{name:'Load more subtasks',exact:true}).click();await expect(s.locator('.project-row')).toHaveCount(22);await expect(s).not.toContainText('SECRET');
 assert.equal(pages.length,2);assert.deepEqual(pages.flatMap(r=>r.data.items.map(i=>i.id)).sort((a,b)=>a-b),data.children.map(i=>i.id).sort((a,b)=>a-b));for(const r of pages)assert.deepEqual(r.object_refs.filter(ref=>ref.kind==='issue').map(ref=>Number(ref.id)).sort((a,b)=>a-b),[data.root.id,...r.data.items.map(i=>i.id)].sort((a,b)=>a-b));
 const audit=snapshot(runPython);for(const rows of Object.values(audit))for(const row of rows)if(row.action_id==='issue.children.list'){for(const ref of row.scope_refs){if(ref.kind==='issue')assert([data.root.id,...data.children.map(i=>i.id)].includes(Number(ref.id)));if(ref.kind==='issue_requirements')assert([data.root.requirements_version_id,...data.children.map(i=>i.requirements_version_id)].includes(Number(ref.id)));}assert(!JSON.stringify(row.scope_refs).includes('r1-private'));assert(!JSON.stringify(row.scope_refs).includes('r1-hidden-requirement'));}
 const titles=await s.locator('.project-row').allTextContents();for(const child of data.children)assert(titles.some(t=>t.includes(child.title)));
 });
 if(!permissions){await measure(async()=>{
 await s.getByLabel('Include archived subtasks',{exact:true}).check();await expect(s.locator('.project-row')).toHaveCount(20);await s.getByRole('button',{name:'Load more subtasks',exact:true}).click();await expect(s.locator('.project-row')).toHaveCount(23);await expect(s).toContainText(data.archived.title);await expect(s).not.toContainText('SECRET');
 const child=data.children[0];await s.getByRole('button',{name:`${child.title} (#${child.id})`,exact:true}).click();await s.getByRole('button',{name:'Show hierarchy',exact:true}).click();await expect(s).toContainText('No visible subtasks.');await s.getByRole('button',{name:`${data.root.title} (#${data.root.id})`,exact:true}).click();await s.getByRole('button',{name:'Show hierarchy',exact:true}).click();await expect(s).toContainText('No parent issue.');
 });console.log('PASS r1_visible_pagination_archived_navigation: real 20+2, archived 23, cross-project navigation and complete row snapshots');}
 else{
 runPython(`from workpal.access.models import SourceGrant;SourceGrant.objects.filter(user_id=2,source__object_id__in=['r1-root','r1-child-requirement']).update(write=False)`);
 await measure(async()=>{await s.getByRole('button',{name:'Refresh hierarchy',exact:true}).click();await expect(s.locator('.project-row')).toHaveCount(20);await expect(s).toContainText(data.children[0].title);});
 runPython(`from workpal.access.models import SourceGrant;SourceGrant.objects.filter(user_id=2,source__object_id='r1-child-requirement').update(read=False)`);
 await measure(async()=>{await s.getByRole('button',{name:'Refresh hierarchy',exact:true}).click();await expect(s.locator('.project-row')).toHaveCount(20);await s.getByRole('button',{name:'Load more subtasks',exact:true}).click();await expect(s.locator('.project-row')).toHaveCount(21);await expect(s).not.toContainText(data.children[0].title);});
 runPython(`from workpal.access.models import SourceGrant;SourceGrant.objects.filter(user_id=2,source__object_id='r1-root').update(read=False)`);
 await measure(async()=>{await s.getByRole('button',{name:'Refresh hierarchy',exact:true}).click();await expect(s).toHaveCount(0);});console.log('PASS r1_independent_permissions_all_tables_readonly: write-only revocation readable, requirement read filtered, root read cleared; all business rows unchanged');
 }
});

await withBrowser(async({base,newPage,runPython,expect})=>{
 const data=decode(runPython(fixture));
 const target=decode(runPython(`import json
from workpal.contracts import Actor
from workpal.work import issues
from workpal.identity.models import Membership
Membership.objects.get_or_create(user_id=2,workspace_id=2,defaults={'role':'member'})
print(json.dumps(issues.create(Actor(1,1),${data.root.project_id},'Independent navigation target')))`));
 for(const destination of ['issue','workspace','logout'])for(const denied of [false,true]){
  const p=await newPage();
  runPython(`from workpal.access.models import SourceGrant;SourceGrant.objects.filter(user_id=2,source__object_id='r1-root').update(read=True,write=True)`);
  await openRoot(p,base,data.root);
  const show=p.getByRole('region',{name:'Issue hierarchy'}).getByRole('button',{name:'Show hierarchy',exact:true});
  await expect(show).toBeVisible();
  let release,arrived,finished,timer,routeError;
  const gate=new Promise(r=>release=r),ready=new Promise(r=>arrived=r),done=new Promise(r=>finished=r);let held=false;
  const pattern='**/actions/issue.read';
  const handler=async route=>{const body=route.request().postDataJSON();if(held||Number(body.payload?.issue_id)!==data.root.id)return route.continue();held=true;try{const response=await route.fetch();assert.equal(response.status(),denied?403:200);arrived();await gate;await route.fulfill({response});}catch(error){routeError=error;arrived();await route.abort().catch(()=>{});}finally{finished();}};
  await p.route(pattern,handler);
  try{
   if(denied)runPython(`from workpal.access.models import SourceGrant;SourceGrant.objects.filter(user_id=2,source__object_id='r1-root').update(read=False,write=False)`);
   await show.click();await Promise.race([ready,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Hierarchy response did not reach hold')),10000);})]);clearTimeout(timer);if(routeError)throw routeError;
   if(destination==='issue'){await p.getByLabel('Search issues').fill(target.title);await p.getByRole('button',{name:`${target.title} (#${target.id})`,exact:true}).click();await expect(p.locator('.issue-detail')).toContainText(target.title);}
   else if(destination==='workspace')await p.getByLabel('Workspace',{exact:true}).selectOption('2');
   else await p.getByRole('button',{name:'Sign out',exact:true}).click();
   release();await done;if(routeError)throw routeError;await p.waitForLoadState('networkidle');
   if(destination==='issue')await expect(p.locator('.issue-detail')).toContainText(target.title);
   else if(destination==='logout')await expect(p.getByRole('button',{name:'Sign in',exact:true})).toBeVisible();
   else await expect(p.getByLabel('Workspace',{exact:true})).toHaveValue('2');
   await expect(p.locator('body')).not.toContainText(data.root.title);
   console.log(`PASS r2_late_${destination}_${denied?'real403':'success'}`);
  }finally{clearTimeout(timer);release();if(held)await done;await p.unroute(pattern,handler);await p.context().close();}
 }
});

async function bounded(promise){let timer;try{return await Promise.race([promise,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Response hold deadline exceeded')),15000);})]);}finally{clearTimeout(timer);}}
// Hold only genuine children responses, after the server has authorized and read
// the requested cursor/filter. Each branch owns its context and releases in finally.
await withBrowser(async({base,newPage,runPython,expect})=>{
 const data=decode(runPython(fixture));
 for(const includeArchived of [false,true])for(const pageKind of ['first','next']){
  const p=await newPage();await openRoot(p,base,data.root);
  const s=p.getByRole('region',{name:'Issue hierarchy'}),filter=s.getByLabel('Include archived subtasks',{exact:true});
  let firstResponse=p.waitForResponse(r=>r.url().endsWith('/actions/issue.children.list')&&r.ok());
  await s.getByRole('button',{name:'Show hierarchy',exact:true}).click();await expect(s.locator('.project-row')).toHaveCount(20);let firstPage=(await (await firstResponse).json()).data;
  if(includeArchived){firstResponse=p.waitForResponse(r=>r.url().endsWith('/actions/issue.children.list')&&r.ok());await filter.check();await expect(s.locator('.project-row')).toHaveCount(20);firstPage=(await (await firstResponse).json()).data;}
  const cursor=pageKind==='first'?0:firstPage.next_cursor;
  let release,arrived,finished,timer,routeError,held=false,oldPage;
  const gate=new Promise(r=>release=r),ready=new Promise(r=>arrived=r),done=new Promise(r=>finished=r),requests=[];
  const pattern='**/actions/issue.children.list';
  const handler=async route=>{
   const payload=route.request().postDataJSON().payload;requests.push(payload);
   if(held||Number(payload.issue_id)!==data.root.id||payload.cursor!==cursor||payload.include_archived!==includeArchived)return route.continue();
   held=true;
   try{const response=await route.fetch({timeout:10000});assert.equal(response.status(),200);oldPage=(await response.json()).data;assert.equal(oldPage.items.length,cursor===0?20:includeArchived?3:2);arrived();await bounded(gate);await route.fulfill({response});}
   catch(error){routeError=error;arrived();await route.abort().catch(()=>{});}finally{finished();}
  };
  await p.route(pattern,handler);
  try{
   const before=snapshot(runPython);
   await s.getByRole('button',{name:cursor?'Load more subtasks':'Refresh hierarchy',exact:true}).click();
   await Promise.race([ready,new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Children response did not reach hold')),10000);})]);clearTimeout(timer);if(routeError)throw routeError;
   const nextFirstResponse=p.waitForResponse(r=>r.url().endsWith('/actions/issue.children.list')&&r.ok());
   await filter.setChecked(!includeArchived);await expect(s.locator('.project-row')).toHaveCount(20);const nextFirst=(await (await nextFirstResponse).json()).data;
   assert(requests.some(r=>r.cursor===0&&r.include_archived===!includeArchived),'filter change starts at cursor zero');
   release();await bounded(done);if(routeError)throw routeError;await p.waitForLoadState('networkidle');
   await expect(s.locator('.project-row')).toHaveCount(20);await expect(filter).toBeChecked({checked:!includeArchived});
   await expect(s.getByRole('button',{name:'Retry',exact:true})).toHaveCount(0);
   await s.getByRole('button',{name:'Load more subtasks',exact:true}).click();await expect(s.locator('.project-row')).toHaveCount(includeArchived?22:23);
   assert(requests.some(r=>r.cursor===nextFirst.next_cursor&&r.include_archived===!includeArchived),'new filter retains its own next cursor');
   const expected=[...data.children,...(!includeArchived?[data.archived]:[])];
   assert.deepEqual((await s.locator('.project-row button').allTextContents()).sort(),expected.map(i=>`${i.title} (#${i.id})`).sort());
   await expect(s).not.toContainText('SECRET');await expect(s.getByRole('button',{name:'Load more subtasks',exact:true})).toBeHidden();
   unchanged(before,snapshot(runPython));
  }finally{clearTimeout(timer);release();if(held)await bounded(done);await p.unroute(pattern,handler);await p.context().close();}
 }
 console.log('PASS r2_filter_load_more_out_of_order: both filters, first/next page real held responses; reset, exact rows, cursors and all-table read-only checks');
});

await withBrowser(async({base,newPage,runPython,expect,repo})=>{
 const longFixture=fixture.replace("f'R1 child {n:02d}'","f'R1 child {n:02d}' + (' <img src=x onerror=alert(1)> & ' + 'W'*180 if n == 0 else '')");
 const data=decode(runPython(longFixture)),p=await newPage();await openRoot(p,base,data.root);
 const s=p.getByRole('region',{name:'Issue hierarchy'});
 // Move only through the browser tab order; never focus the destination directly.
 async function tabTo(target){for(let n=0;n<100;n++){if(await target.evaluate(el=>el===document.activeElement))return;await p.keyboard.press('Tab');}throw Error('Keyboard target unreachable: '+await target.textContent());}
 await tabTo(s.getByRole('button',{name:'Show hierarchy',exact:true}));await p.keyboard.press('Enter');await expect(s.getByRole('button',{name:'Refresh hierarchy',exact:true})).toBeFocused();await expect(s.locator('.project-row')).toHaveCount(20);
 await tabTo(s.getByRole('button',{name:'Load more subtasks',exact:true}));await p.keyboard.press('Enter');await expect(s.locator('.project-row')).toHaveCount(22);
 await expect(s.locator('.project-row').nth(20).getByRole('button')).toBeFocused();
 const child=data.children[0];await tabTo(s.getByRole('button',{name:`${child.title} (#${child.id})`,exact:true}));await p.keyboard.press('Enter');
 await expect(p.locator('.issue-detail').getByRole('heading',{name:`Issue #${child.id}`,exact:true})).toBeFocused();
 await tabTo(s.getByRole('button',{name:'Show hierarchy',exact:true}));await p.keyboard.press('Enter');await expect(s).toContainText('No visible subtasks.');
 await tabTo(s.getByRole('button',{name:`${data.root.title} (#${data.root.id})`,exact:true}));await p.keyboard.press('Enter');await expect(p.locator('.issue-detail').getByRole('heading',{name:`Issue #${data.root.id}`,exact:true})).toBeFocused();
 await tabTo(s.getByRole('button',{name:'Show hierarchy',exact:true}));await p.keyboard.press('Enter');await expect(s.locator('.project-row')).toHaveCount(20);
 const filter=s.getByLabel('Include archived subtasks',{exact:true});await tabTo(filter);await p.keyboard.press('Space');await expect(filter).toBeChecked();await expect(s.locator('.project-row')).toHaveCount(20);
 await tabTo(s.getByRole('button',{name:'Refresh hierarchy',exact:true}));await p.keyboard.press('Enter');await expect(s.getByRole('button',{name:'Refresh hierarchy',exact:true})).toBeFocused();await expect(s.locator('.project-row')).toHaveCount(20);
 await tabTo(s.getByRole('button',{name:'Load more subtasks',exact:true}));await p.keyboard.press('Enter');await expect(s.locator('.project-row')).toHaveCount(23);await expect(s.locator('.project-row').nth(20).getByRole('button')).toBeFocused();

 // A completed old navigation must not reclaim focus from the newer detail.
 let release,arrived,finished,held=false,routeError;
 const gate=new Promise(r=>release=r),ready=new Promise(r=>arrived=r),done=new Promise(r=>finished=r);
 const pattern='**/actions/issue.read';
 const handler=async route=>{
  if(held||Number(route.request().postDataJSON().payload?.issue_id)!==child.id)return route.continue();held=true;
  try{const response=await route.fetch({timeout:10000});assert.equal(response.status(),200);arrived();await bounded(gate);await route.fulfill({response});}
  catch(error){routeError=error;arrived();await route.abort().catch(()=>{});}finally{finished();}
 };
 await p.route(pattern,handler);
 try{
  await tabTo(s.getByRole('button',{name:`${child.title} (#${child.id})`,exact:true}));await p.keyboard.press('Enter');await bounded(ready);if(routeError)throw routeError;
  await p.getByRole('button',{name:`${data.root.title} (#${data.root.id})`,exact:true}).click();
  const show=s.getByRole('button',{name:'Show hierarchy',exact:true});await expect(show).toBeVisible();await tabTo(show);
  release();await bounded(done);if(routeError)throw routeError;await p.waitForLoadState('networkidle');await expect(show).toBeFocused();await expect(p.locator('.issue-detail')).toContainText(data.root.title);
  await p.keyboard.press('Enter');await expect(s.locator('.project-row')).toHaveCount(20);
  await tabTo(s.getByLabel('Include archived subtasks',{exact:true}));await p.keyboard.press('Space');await expect(s.locator('.project-row')).toHaveCount(20);
  await tabTo(s.getByRole('button',{name:'Load more subtasks',exact:true}));await p.keyboard.press('Enter');await expect(s.locator('.project-row')).toHaveCount(23);
 }finally{release();if(held)await bounded(done);await p.unroute(pattern,handler);}
 const {mkdir}=await import('node:fs/promises');await mkdir(repo+'/outputs/workpal-web',{recursive:true});
 for(const [name,width] of [['desktop',1440],['mobile',390]]){await p.setViewportSize({width,height:1000});assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await p.screenshot({path:repo+`/outputs/workpal-web/a54d2-hierarchy-${name}.png`,fullPage:true});assert.equal(await s.locator('img,script').count(),0);await expect(s).toContainText(data.children[0].title);}
 console.log('PASS r2_keyboard_hierarchy_navigation: Tab/Enter/Space, Show and pagination focus, child/parent heading focus, 1440/390 without overflow');
});

await withBrowser(async({base,newPage,runPython,expect})=>{
 const data=decode(runPython(fixture)),p=await newPage();await openRoot(p,base,data.root);
 const s=p.getByRole('region',{name:'Issue hierarchy'}),child=data.children[0];
 await s.getByRole('button',{name:'Show hierarchy',exact:true}).click();await expect(s.locator('.project-row')).toHaveCount(20);
 runPython("from workpal.access.models import SourceGrant;SourceGrant.objects.filter(user_id=2,source__object_id='r1-child-requirement').update(read=False,write=False)");
 let release,arrived,finished,held=false,routeError;
 const gate=new Promise(r=>release=r),ready=new Promise(r=>arrived=r),done=new Promise(r=>finished=r),pattern='**/actions/issue.read';
 const handler=async route=>{
  if(held||Number(route.request().postDataJSON().payload?.issue_id)!==child.id)return route.continue();held=true;
  try{const response=await route.fetch({timeout:10000});assert.equal(response.status(),403);arrived();await bounded(gate);await route.fulfill({response});}
  catch(error){routeError=error;arrived();await route.abort().catch(()=>{});}finally{finished();}
 };
 await p.route(pattern,handler);
 try{
  const before=snapshot(runPython);
  await s.getByRole('button',{name:`${child.title} (#${child.id})`,exact:true}).click();await bounded(ready);if(routeError)throw routeError;
  await p.getByRole('button',{name:`${data.root.title} (#${data.root.id})`,exact:true}).click();
  const show=s.getByRole('button',{name:'Show hierarchy',exact:true});await expect(show).toBeVisible();await show.focus();
  release();await bounded(done);if(routeError)throw routeError;await p.waitForLoadState('networkidle');
  await expect(show).toBeFocused();await expect(p.locator('.issue-detail')).toContainText(data.root.title);
  await expect(p.locator('.issue-detail')).not.toContainText(child.title);unchanged(before,snapshot(runPython));
  console.log('PASS r2_late_navigation_real403: rejected former child navigation cannot clear or steal focus from the current detail');
 }finally{release();if(held)await bounded(done);await p.unroute(pattern,handler);}
});
