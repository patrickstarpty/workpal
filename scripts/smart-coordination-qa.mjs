import assert from 'node:assert/strict';
import {chromium,expect} from '@playwright/test';
const browser=await chromium.launch(),base='http://127.0.0.1:4174';
try{
 const page=await browser.newPage();await page.goto(base);await page.getByRole('button',{name:'Sign in',exact:true}).click();await expect(page.getByRole('button',{name:'Enter Workspace',exact:true})).toBeVisible();
 const headers={'X-Workspace-Slug':'workpal-team'};
 const get=async path=>{const r=await page.request.get(base+path,{headers});assert.equal(r.status(),200,path);return r.json();};
 const {issues}=await get('/api/issues'),agents=await get('/api/agents'),squads=await get('/api/squads');assert.equal(squads.length,5);
 assert.equal(issues.filter(i=>i.assignee_type==='squad').length,16);assert.equal(issues.filter(i=>i.assignee_type==='agent').length,5);
 for(const target of [...squads.map(s=>({...s,type:'squad'})),...agents.map(a=>({...a,type:'agent'}))]){
  const data=await get(`/api/issues?assignee_filters=${target.type}:${target.id}`);
  const expected=issues.filter(i=>i.assignee_type===target.type&&i.assignee_id===target.id).map(i=>i.id).sort();
  assert.deepEqual(data.issues.map(i=>i.id).sort(),expected);assert.equal(data.total,expected.length);
 }
 for(const [id,kind,name,current] of [['workflow-work-07','agent','Implementation Engineer','Engineering delivery'],['workflow-work-07','squad','Engineering delivery','Implementation Engineer']]){
  const before=await get(`/api/issues/${id}/timeline`);
  await page.evaluate(identifier=>{location.hash='/workpal-team/issues/'+identifier;},issues.find(i=>i.id===id).identifier);
  const trigger=page.getByRole('button',{name:new RegExp('^'+current)}).first();await trigger.click();
  await page.getByPlaceholder('Assign to...').fill(name);
  const option=page.getByRole('button',{name:kind==='squad'?name:new RegExp(name+'.*'+name)}).last();
  await expect(option).toBeEnabled();
  const saved=page.waitForResponse(r=>r.url().endsWith('/api/issues/'+id)&&['PUT','PATCH'].includes(r.request().method()));await page.getByPlaceholder('Assign to...').press('Enter');await page.getByRole('button',{name:'Confirm assignment',exact:true}).click();assert.equal((await saved).status(),200);
  const after=await get(`/api/issues/${id}/timeline`);
  assert.equal(after.length,before.length+1);
  const latest=after.filter(e=>e.action==='assignee_changed').at(-1);assert.equal(latest.details.to_type,kind);
 }
 await page.evaluate(()=>{location.hash='/workpal-team/squads/workflow-delivery';});
 await expect(page.getByText('Deliver upload interruption recovery',{exact:true}).first()).toBeVisible();
 await expect(page.getByText('Design upload recovery interactions',{exact:true})).toHaveCount(0);
 console.log('PASS: 5 squads; 16 squad / 5 individual tickets; all typed filters; both picker paths; correct squad recent work');
}finally{await browser.close();}
