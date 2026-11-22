import assert from 'node:assert/strict';
import {chromium, expect} from '@playwright/test';
const base=process.env.WORKPAL_QA_URL||'http://127.0.0.1:4174';
const browser=await chromium.launch();
try {
 const page=await browser.newPage();
 await page.goto(base);
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 const panel=page.getByRole('region',{name:'Workflow tickets'});
 await expect(panel.getByText('4 tickets',{exact:true})).toBeVisible();
 const response=await page.request.get(base+'/api/issues',{headers:{'X-Workspace-Slug':'workpal-team'}});
 assert.equal(response.status(),200);
 const {issues}=await response.json();assert.equal(issues.length,21);
 for(const key of ['backlog','todo','in_progress','in_review','done','blocked','cancelled']){
  assert.equal(issues.filter(i=>i.status===key).length,3);
 }
 for(const [index,stage] of ['plan','design','build','test','deploy','maintain'].entries()){
  await page.locator('.stages button').nth(index).click();
  const count=issues.filter(i=>i.metadata.workflow_stage===stage).length;
  await expect(panel.getByText(`${count} tickets`,{exact:true})).toBeVisible();
 }
 await panel.getByLabel('Include all stages').check();
 await panel.getByLabel('Work status').selectOption('in_progress');
 await expect(panel.getByText('3 tickets',{exact:true})).toBeVisible();
 await panel.getByRole('link',{name:/Deliver upload interruption recovery/}).click();
 await expect(page.getByText('Deliver upload interruption recovery',{exact:true}).first()).toBeVisible();
 await page.evaluate(()=>{location.hash='/home';});
 await expect(panel).toBeVisible();
 await page.setViewportSize({width:390,height:844});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
 console.log('PASS: 21 persisted tickets, all stage/status groups, ticket deep link, narrow layout');
} finally {await browser.close();}
