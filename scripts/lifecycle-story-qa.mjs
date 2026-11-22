import assert from 'node:assert/strict';
import {chromium, expect} from '@playwright/test';
const base=process.env.WORKPAL_QA_URL||'http://127.0.0.1:4174';
const browser=await chromium.launch();
try {
 const page=await browser.newPage(); const errors=[];
 page.on('pageerror',e=>{errors.push(e.message);console.log('PAGEERROR',e.stack);});
 await page.goto(base);
 await expect(page.getByLabel('Email',{exact:true})).toHaveValue('workpal@fwd.com');
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page.getByRole('button',{name:'Enter Workspace',exact:true})).toBeVisible();
 const headers={'X-Workspace-Slug':'review'};
 const get=async path=>{const r=await page.request.get(base+path,{headers});assert.equal(r.status(),200,path);return r.json();};
 const issues=(await get('/api/issues')).issues;
 assert.equal(issues.length,7);
 const agents=new Set((await get('/api/agents')).map(a=>a.id));
 let totalRuns=0,totalEvents=0,totalMessages=0;
 for(const stage of ['plan','design','build','test','deploy','maintain']){
  const id='lifecycle-'+stage,issue=issues.find(i=>i.id===id);assert(issue);
  assert.equal(issue.parent_issue_id,'lifecycle-delivery');assert(agents.has(issue.assignee_id));
  const timeline=await get(`/api/issues/${id}/timeline`);
  assert(timeline.length>=15);totalEvents+=timeline.length;
  assert(timeline.every((e,i)=>!i||e.created_at>=timeline[i-1].created_at));
  assert.equal(timeline.filter(e=>e.action==='status_changed').at(-1).details.to,issue.status);
  for(const entry of timeline)if(entry.actor_type==='agent')assert(agents.has(entry.actor_id));
  const runs=await get(`/api/issues/${id}/task-runs?view=timeline`);totalRuns+=runs.length;
  for(const run of runs){
   assert(agents.has(run.agent_id));
   const messages=await get(`/api/tasks/${run.id}/messages`);assert(messages.length>=7);totalMessages+=messages.length;
   assert(messages.every((m,i)=>m.seq===i+1&&m.created_at>=run.started_at&&m.created_at<=run.completed_at));
   assert.equal(messages.at(-1).type,run.status==='failed'?'error':'text');
  }
  if(stage==='build'){
   const failed=runs.find(r=>r.status==='failed'),retry=runs.find(r=>r.attempt===2);
   assert(failed&&retry);assert.equal(retry.attribution.retry_of_task_id,failed.id);
   assert(retry.started_at>failed.completed_at);
  }
  const attachments=await get(`/api/issues/${id}/attachments`);assert.equal(attachments.length,2);
  for(const a of attachments){const r=await page.request.get(base+a.url);assert.equal(r.status(),200);assert.equal(Buffer.byteLength(await r.text()),a.size_bytes);}
  await page.evaluate(id=>{location.hash='/review/issues/'+id;},id);
  await expect(page.getByText(issue.title,{exact:true}).first()).toBeVisible();

  await page.getByRole('button',{name:'Jump to latest',exact:true}).click();
  await expect(page.getByText('Owner decision',{exact:true}).first()).toBeVisible();
  console.log(stage,JSON.stringify({events:timeline.length,runs:runs.length,artifacts:attachments.length}));
 }
 assert.equal((await get('/api/issues/lifecycle-delivery/task-runs?scope=subtree')).length,totalRuns);
 await page.evaluate(()=>{location.hash='/review/issues/lifecycle-build';});
 await expect(page.getByText('03 Build — Workflow team delivery',{exact:true}).first()).toBeVisible();
 await page.getByText('Address the review and prepare revision 2.',{exact:true}).last().hover();
 await page.getByRole('button',{name:'View transcript',exact:true}).first().click();
 await expect(page.getByRole('dialog').last()).toBeVisible();
 await expect(page.getByRole('dialog').last().getByText('Bash',{exact:true}).first()).toBeVisible();
 await page.keyboard.press('Escape');
 await page.getByRole('button',{name:/implementation-report\.mdv2/}).click();
 await expect(page.getByRole('dialog').last().getByText('Change set',{exact:true})).toBeVisible();
 await expect(page.getByRole('dialog').last().getByText('Review finding B-01',{exact:true})).toBeVisible();
 console.log('ARTIFACT PREVIEW', (await page.getByRole('dialog').last().innerText()).slice(0,1400));
 assert.deepEqual(errors,[]);
 console.log('PASS',JSON.stringify({issues:issues.length,runs:totalRuns,events:totalEvents,messages:totalMessages}));
}finally{await browser.close();}
