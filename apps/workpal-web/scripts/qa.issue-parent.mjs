import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {withBrowser,signIn} from './browser-fixture.mjs';
await withBrowser(async({base,newPage,runPython,expect,repo})=>{
 const py=c=>JSON.parse(runPython(c).trim().split('\n').at(-1));
 const f=py(`import json
from workpal.contracts import Actor
from workpal.work import service,issues
a=Actor(1,1);p=service.create(a,'Parent A project');q=service.create(a,'Parent B project');pa=issues.create(a,p['id'],'Parent A');pb=issues.create(a,q['id'],'Parent B');c=issues.create(a,p['id'],'Moving child',parent_issue_id=pa['id'])
print(json.dumps(dict(a=pa,b=pb,c=c)))`);
 const snapshot=()=>py(`import json
from django.apps import apps
print(json.dumps({m._meta.label:list(m.objects.order_by('pk').values()) for m in apps.get_models() if m._meta.app_label not in ['sessions']},default=str))`);
 const before=snapshot();
 async function open(p){await signIn(p,base,'reader');await p.getByLabel('Workspace',{exact:true}).selectOption('1');await p.getByRole('button',{name:'Issues',exact:true}).click();await p.getByLabel('Search issues').fill(f.c.title);await p.getByRole('button',{name:`${f.c.title} (#${f.c.id})`,exact:true}).click();const s=p.getByRole('region',{name:'Issue hierarchy'});await s.getByRole('button',{name:'Show hierarchy',exact:true}).click();return s;}
 const p=await newPage(),s=await open(p);
 await s.getByRole('button',{name:'Change parent',exact:true}).click();let d=p.getByRole('dialog',{name:'Change parent',exact:true});
 await expect(d).toContainText(`Current parent: ${f.a.title} (#${f.a.id})`);
 await mkdir(repo+'/outputs/workpal-web',{recursive:true});for(const [name,width] of [['desktop',1440],['mobile',390]]){await p.setViewportSize({width,height:1000});assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await p.screenshot({path:repo+`/outputs/workpal-web/a54d2-parent-${name}.png`});}
 await d.getByLabel('Search parent issues').fill(f.b.title);await d.getByRole('button',{name:`${f.b.title} (#${f.b.id})`,exact:true}).click();await d.getByRole('button',{name:'Save parent',exact:true}).click();await expect(d).not.toBeVisible();await s.getByRole('button',{name:'Show hierarchy',exact:true}).click();await expect(s.getByRole('button',{name:`${f.b.title} (#${f.b.id})`,exact:true})).toBeVisible();
 const moved=snapshot();const p2=await newPage(),s2=await open(p2);await expect(s2.getByRole('button',{name:`${f.b.title} (#${f.b.id})`,exact:true})).toBeVisible();
 await s2.getByRole('button',{name:'Change parent',exact:true}).click();d=p2.getByRole('dialog',{name:'Change parent',exact:true});await expect(d).toContainText(`Current parent: ${f.b.title} (#${f.b.id})`);await d.getByRole('button',{name:'Remove parent',exact:true}).click();await d.getByRole('button',{name:'Save parent',exact:true}).click();await expect(d).not.toBeVisible();await s2.getByRole('button',{name:'Show hierarchy',exact:true}).click();await expect(s2).toContainText('No parent issue.');const detached=snapshot();await s.getByRole('button',{name:'Refresh hierarchy',exact:true}).click();await expect(s).toContainText('No parent issue.');const reread=snapshot();
 for(const table of Object.keys(detached).filter(t=>t.endsWith('.SourceLink')||t.endsWith('.Outbox')||t.endsWith('.IdempotencyResult')))assert.deepEqual(reread[table],detached[table],`reread ${table}`);
 const links=moved['access.SourceLink'].filter(r=>!before['access.SourceLink'].some(x=>x.id===r.id));const objects=moved['access.RegisteredObject'];assert.equal(objects.find(r=>r.id===links[0].derived_id).object_id,String(f.c.id));assert.equal(objects.find(r=>r.id===links[0].source_id).object_id,String(f.b.id));assert.deepEqual(detached['access.SourceLink'],moved['access.SourceLink']);
 for(const [state,n,parent] of [[moved,1,f.b.id],[detached,2,null],[reread,2,null]])for(const [table,rows] of Object.entries(before)){
 const actual=state[table];if(table==='auth.User'){const clean=rs=>rs.map(r=>{const x={...r};delete x.last_login;return x;});assert.deepEqual(clean(actual),clean(rows));}else if(table.endsWith('.Issue')){const expected=structuredClone(rows);const child=expected.find(r=>r.id===f.c.id);child.parent_id=parent;child.revision+=n;const got=structuredClone(actual);delete child.updated_at;delete got.find(r=>r.id===f.c.id).updated_at;assert.deepEqual(got,expected,table);}else if(table.endsWith('.SourceLink')){for(const row of rows)assert(actual.some(r=>JSON.stringify(r)===JSON.stringify(row)));assert.equal(actual.length,rows.length+1,table);}else if(['.AuditEvent','.Outbox','.IdempotencyResult'].some(x=>table.endsWith(x))){for(const row of rows)assert(actual.some(r=>JSON.stringify(r)===JSON.stringify(row)));const business=actual.filter(r=>r.action_id==='issue.set_parent');assert.equal(business.length,rows.filter(r=>r.action_id==='issue.set_parent').length+n,table);if(!table.endsWith('.AuditEvent'))assert.equal(actual.length,rows.length+n,table);else console.log('READ AUDIT',actual.filter(r=>r.action_id!=='issue.set_parent').length-rows.filter(r=>r.action_id!=='issue.set_parent').length);}else assert.deepEqual(actual,rows,table);
 }
 console.log('PASS reparent_detach_sql_persistence: member, independent contexts, two writes, full SQL facts and reread');
});
