import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {withBrowser,signIn} from './browser-fixture.mjs';
await withBrowser(async({base,newPage,runPython,expect,repo})=>{
 const issue=JSON.parse(runPython(`import json
from workpal.contracts import Actor
from workpal.work import service,issues
a=Actor(1,1);p=service.create(a,'Hierarchy reader');i=issues.create(a,p['id'],'Hierarchy reader root');q=service.create(a,'Hierarchy cross project')
for n in range(22):issues.create(a,q['id'],f'Child {n:02d} <img src=x onerror=alert(1)>',parent_issue_id=i['id'])
print(json.dumps(i))`).trim().split('\n').at(-1));
 const p=await newPage();await signIn(p,base,'reader');await p.getByLabel('Workspace',{exact:true}).selectOption('1');await p.getByRole('button',{name:'Issues',exact:true}).click();await p.getByLabel('Search issues').fill(issue.title);await p.getByRole('button',{name:`${issue.title} (#${issue.id})`,exact:true}).click();await expect(p.getByRole('region',{name:'Issue hierarchy'})).toBeVisible();const section=p.getByRole('region',{name:'Issue hierarchy'});await section.getByRole('button',{name:'Show hierarchy',exact:true}).click();await expect(section.locator('.project-row')).toHaveCount(20);await expect(section).toContainText('No parent issue.');await section.getByRole('button',{name:'Load more subtasks',exact:true}).click();await expect(section.locator('.project-row')).toHaveCount(22);await section.getByLabel('Include archived subtasks',{exact:true}).check();await expect(section.locator('.project-row')).toHaveCount(20);
 await p.route('**/actions/issue.children.list',r=>r.abort());await section.getByRole('button',{name:'Refresh hierarchy',exact:true}).click();await expect(section.getByRole('button',{name:'Retry',exact:true})).toBeVisible();await expect(section).not.toContainText('No visible subtasks.');await p.unroute('**/actions/issue.children.list');await section.getByRole('button',{name:'Retry',exact:true}).click();await expect(section.locator('.project-row')).toHaveCount(20);
 const nextParent=JSON.parse(runPython(`import json
from workpal.contracts import Actor
from workpal.work import issues,hierarchy
a=Actor(1,1);child=issues.read(a,${issue.id});parent=issues.create(a,child['project_id'],'Updated parent after reading')
hierarchy.set_parent(a,child['id'],parent['id'],child['revision'])
print(json.dumps(parent))`).trim().split('\n').at(-1));
 await section.getByRole('button',{name:'Refresh hierarchy',exact:true}).click();await expect(section.getByRole('button',{name:`${nextParent.title} (#${nextParent.id})`,exact:true})).toBeVisible();
 await mkdir(repo+'/outputs/workpal-web',{recursive:true});for(const [name,width] of [['desktop',1440],['mobile',390]]){await p.setViewportSize({width,height:1000});assert.equal(await section.locator('img,script').count(),0);assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await p.screenshot({path:repo+`/outputs/workpal-web/a54d2-hierarchy-${name}.png`});}console.log('PASS member_parent_children_navigation_pagination: real cross-project 20+2, current parent refresh, filter reset, network Retry, text and viewport');
});
