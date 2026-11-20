import assert from 'node:assert/strict';
import {withBrowser,signIn} from './browser-fixture.mjs';
await withBrowser(async({base,newPage,runPython,expect,repo})=>{
 const py=c=>JSON.parse(runPython(c).trim().split('\n').at(-1));
 const f=py(`import json
from workpal.contracts import Actor
from workpal.work import service,issues
a=Actor(1,1);p=service.create(a,'Recovery');pa=issues.create(a,p['id'],'Recovery parent');c=issues.create(a,p['id'],'Recovery child')
print(json.dumps(dict(p=pa,c=c)))`);
 const p=await newPage();await signIn(p,base,'reader');await p.getByLabel('Workspace',{exact:true}).selectOption('1');await p.getByRole('button',{name:'Issues',exact:true}).click();await p.getByLabel('Search issues').fill(f.c.title);await p.getByRole('button',{name:`${f.c.title} (#${f.c.id})`,exact:true}).click();const s=p.getByRole('region',{name:'Issue hierarchy'});await s.getByRole('button',{name:'Show hierarchy',exact:true}).click();await s.getByRole('button',{name:'Change parent',exact:true}).click();const d=p.getByRole('dialog',{name:'Change parent',exact:true});await expect(d).toContainText('No parent issue.');await d.getByLabel('Search parent issues').fill(f.p.title);await d.getByRole('button',{name:`${f.p.title} (#${f.p.id})`,exact:true}).click();
 py(`import json
from workpal.contracts import Actor
from workpal.work import hierarchy
hierarchy.set_parent(Actor(1,1),${f.c.id},${f.p.id},${f.c.revision})
print(json.dumps(True))`);
 await d.getByRole('button',{name:'Save parent',exact:true}).click();await expect(d.getByRole('button',{name:'Reload current',exact:true})).toBeVisible();await expect(d.getByRole('button',{name:'Save parent',exact:true})).toBeDisabled();await d.getByRole('button',{name:'Reload current',exact:true}).click();await expect(d.getByRole('button',{name:'Refresh issue',exact:true})).toBeVisible();await expect(d.getByRole('button',{name:'Save parent',exact:true})).toBeDisabled();for(const [name,width] of [['desktop',1440],['mobile',390]]){await p.setViewportSize({width,height:1000});assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await p.screenshot({path:repo+`/outputs/workpal-web/a54d2-parent-recovery-${name}.png`});}console.log('PASS conflict_target_already_achieved');
 await d.getByRole('button',{name:'Refresh issue',exact:true}).click();await expect(d).not.toBeVisible();await s.getByRole('button',{name:'Show hierarchy',exact:true}).click();await s.getByRole('button',{name:'Change parent',exact:true}).click();await expect(d).toContainText('Current parent:');await d.getByRole('button',{name:'Remove parent',exact:true}).click();
 const requests=[];let first=true;const handler=async r=>{requests.push(r.request().postDataJSON());if(first){first=false;const response=await r.fetch({timeout:10000});assert.equal(response.status(),200);await r.abort();}else await r.continue();};await p.route('**/actions/issue.set_parent',handler);
 try{await d.getByRole('button',{name:'Save parent',exact:true}).click();await expect(d.getByRole('button',{name:'Retry original request',exact:true})).toBeEnabled();await expect(d.getByLabel('Search parent issues')).toBeDisabled();await d.getByRole('button',{name:'Cancel',exact:true}).click();await s.getByRole('button',{name:'Change parent',exact:true}).click();await expect(d.getByRole('button',{name:'Retry original request',exact:true})).toBeEnabled();await d.getByRole('button',{name:'Retry original request',exact:true}).click();await expect(d).not.toBeVisible();assert.equal(requests.length,2);assert.deepEqual(requests[0],requests[1]);console.log('PASS detach_lost_response_reopen_original_request');}finally{await p.unroute('**/actions/issue.set_parent',handler);}

});
