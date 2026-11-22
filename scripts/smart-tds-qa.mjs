import {chromium,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
import assert from 'node:assert/strict';
const rows=JSON.parse(await readFile('docs/handoffs/smart-tds-publication.json','utf8'));const browser=await chromium.launch();
try{const page=await browser.newPage();await page.goto('http://127.0.0.1:4174');await page.getByRole('button',{name:'Sign in',exact:true}).click();await expect(page.getByRole('button',{name:'Enter Workspace',exact:true})).toBeVisible();
for(const row of rows){
 await page.evaluate(r=>{location.hash='/workpal-team/issues/'+r.ticket+'#comment-'+r.activity_id;},row);
 const comment=page.locator(`[id="comment-${row.activity_id}"]`);await expect(comment).toBeVisible();
 const card=comment.getByRole('button',{name:row.filename,exact:false}).first();await expect(card).toBeVisible();
 const downloading=page.waitForEvent('download');await card.click();const download=await downloading;
 assert.equal(download.suggestedFilename(),row.filename);await download.saveAs('/tmp/'+row.filename);
 assert.deepEqual(await readFile('/tmp/'+row.filename),await readFile('apps/web/public/delivery/tds/'+row.filename));
 console.log('PASS',row.ticket,row.filename,'Activity download matches original DOCX');
}}finally{await browser.close();}
