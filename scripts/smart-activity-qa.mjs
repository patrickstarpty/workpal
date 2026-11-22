import assert from 'node:assert/strict';
import {chromium,expect} from '@playwright/test';
const base='http://127.0.0.1:4174';const browser=await chromium.launch();
try {
 const page=await browser.newPage();await page.goto(base);await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page.getByRole('button',{name:'Enter Workspace',exact:true})).toBeVisible();
 const headers={'X-Workspace-Slug':'workpal-team'};
 const get=async path=>{const r=await page.request.get(base+path,{headers});assert.equal(r.status(),200,path);return r.json();};
 const {issues}=await get('/api/issues');const agents=new Set((await get('/api/agents')).map(a=>a.id));
 let runs=0,events=0,artifacts=0;
 for(const issue of issues){
  const timeline=await get(`/api/issues/${issue.id}/timeline`);assert(timeline.length>=8,`${issue.identifier}: missing Activity`);
  assert(timeline.every((e,i)=>!i||e.created_at>=timeline[i-1].created_at));
  assert.equal(timeline.filter(e=>e.action==='status_changed').at(-1).details.to,issue.status);
  assert(timeline.filter(e=>e.action==='status_changed').every(e=>e.details.from!==e.details.to));
  for(const e of timeline)if(e.actor_type==='agent')assert(agents.has(e.actor_id));
  const tasks=await get(`/api/issues/${issue.id}/task-runs`);
  if(['backlog','todo'].includes(issue.status))assert.equal(tasks.length,0);else assert(tasks.length>=2,issue.identifier);
  for(const task of tasks){assert(agents.has(task.agent_id));const messages=await get(`/api/tasks/${task.id}/messages`);assert(messages.length>=5);}
  const attachments=await get(`/api/issues/${issue.id}/attachments`);assert(attachments.length>=1,issue.identifier);
  for(const attachment of attachments){
   const content=await page.request.get(base+`/api/attachments/${attachment.id}/content`,{headers});assert.equal(content.status(),200);
   assert.equal(Buffer.byteLength(await content.text()),attachment.size_bytes);
  }
  await page.evaluate(id=>{location.hash='/workpal-team/issues/'+id;},issue.id);
  await expect(page.getByText(issue.title,{exact:true}).first()).toBeVisible();
  await expect(page.getByText('Requested outcome',{exact:true}).first()).toBeVisible();
  events+=timeline.length;runs+=tasks.length;artifacts+=attachments.length;
 }
 await page.evaluate(()=>{location.hash='/workpal-team/issues/workflow-work-07';});
 await page.getByRole('button',{name:'Jump to latest',exact:true}).click();
 await expect(page.getByText('Next action',{exact:true}).first()).toBeVisible();
 await page.evaluate(()=>{location.hash='/workpal-team/issues/workflow-work-10';});
 await expect(page.getByRole('button',{name:/work-record\.md, version 2/})).toBeVisible();
 await page.getByRole('button',{name:/work-record\.md, version 2/}).click();
 await expect(page.getByRole('dialog').last().getByText('Regression matrix',{exact:true})).toBeVisible();
 await page.keyboard.press('Escape');
 await page.getByText('Address the review for Review upload retry regression coverage',{exact:true}).last().hover();
 await page.getByRole('button',{name:'View transcript',exact:true}).first().click();
 await expect(page.getByRole('dialog').last().getByText('Read',{exact:true}).first()).toBeVisible();
 console.log('PASS',JSON.stringify({tickets:issues.length,events,runs,artifacts}));
}finally{await browser.close();}
