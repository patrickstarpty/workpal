import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {chromium,expect} from '@playwright/test';
const entries=JSON.parse(await readFile('docs/handoffs/smart-deliverables/published-verification.json','utf8'));
const browser=await chromium.launch();const checked=[];
try {
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 await page.goto('http://127.0.0.1:4174');
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page.getByRole('button',{name:'Enter Workspace',exact:true})).toBeVisible();
 const get=async path=>{const r=await page.request.get('http://127.0.0.1:4174'+path,{headers:{'X-Workspace-Slug':'workpal-team'}});assert.equal(r.status(),200,path);return r;};
 for(const entry of entries){
  const inventory=await (await get(`/api/issues/${entry.issue_id}/evidence`)).json();
  const revision=inventory.revisions.find(r=>r.id===entry.revision_id);assert(revision);
  const timeline=await (await get(`/api/issues/${entry.issue_id}/timeline`)).json();
  const comment=timeline.find(c=>c.id===entry.activity_id);assert(comment);
  const attachment=comment.attachments.find(a=>a.id===revision.attachment_id);assert(attachment);
  const content=await (await get(`/api/attachments/${attachment.id}/content`)).text();
  assert.equal(createHash('sha256').update(content).digest('hex'),revision.sha256);
  await page.evaluate(id=>{location.hash='/workpal-team/issues/'+id;},revision.title.split(' ')[0]);
  const evidence=page.getByRole('region',{name:'Delivery evidence'});
  await expect(evidence.getByText(`${revision.title} · v${revision.version} · ${revision.kind}`,{exact:true})).toBeVisible();
  await evidence.getByText(`${revision.title} · v${revision.version} · ${revision.kind}`,{exact:true}).click();
  await evidence.getByRole('button',{name:'View Activity',exact:true}).click();
  const activity=page.locator(`[id="comment-${entry.activity_id}"]`);
  await expect(activity).toBeVisible();
  const file=activity.getByRole('button',{name:attachment.filename,exact:false}).first();
  await expect(file).toBeVisible();await file.click();
  const dialog=page.getByRole('dialog').last();await expect(dialog).toBeVisible();
  // Inspect actual body text, not merely filename or attachment count.
  const heading=content.split('\n').find(line=>line.startsWith('# ')).slice(2);
  await expect(dialog).toContainText(heading.replace(/^SMART-\d+ /,''));
  const section=content.split('\n').find(line=>line.startsWith('## '))?.slice(3);
  if(section) await expect(dialog).toContainText(section.includes('SMART-') ? section.split(':').at(-1).trim() : section);
  await page.keyboard.press('Escape');
  for(const input of revision.input_ids){assert(inventory.inputs[input]);}
  const historical=timeline.find(c=>c._fixture && c.type==='comment');
  if(historical){
   await page.evaluate(({id,comment})=>{location.hash='/workpal-team/issues/'+id+'#comment-'+comment;},{id:revision.title.split(' ')[0],comment:historical.id});
   const old=page.locator(`[id="comment-${historical.id}"]`);
   await expect(old).toBeVisible();
   const link=old.locator(`a[href$="#comment-${entry.activity_id}"]`).first();
   await expect(link).toBeVisible();console.log("LINK",await link.getAttribute("href"));await link.click();console.log("DEST",page.url());
   await expect(page.locator(`[id="comment-${entry.activity_id}"]`)).toBeVisible();
  }
  checked.push({ticket:entry.issue_id,revision:revision.id,activity:comment.id,sha256:revision.sha256,historicalLinkChecked:!!historical,previewHeading:heading,inputs:revision.input_ids.length});
  console.log('PASS',entry.issue_id,'Activity preview:',heading);
 }
 await page.setViewportSize({width:390,height:844});
 await page.getByRole('button',{name:'Toggle right sidebar',exact:true}).click();
 await expect(page.getByRole('region',{name:'Delivery evidence'})).toBeVisible();
 await page.screenshot({path:'/tmp/smart-deliverables-mobile.png'});
 await writeFile('docs/handoffs/smart-deliverables/browser-verification.json',JSON.stringify({checked,narrowScreenSidebar:true},null,2)+'\n');
} finally {await browser.close();}
