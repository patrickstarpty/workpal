import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
import {createServer} from '../server/api.mjs';
const require=createRequire(import.meta.url);
const {chromium,expect}=require(process.env.WORKPAL_PLAYWRIGHT||'@playwright/test');
const server=createServer({dbPath:':memory:'});await new Promise(r=>server.listen(0,'127.0.0.1',r));
const base=`http://127.0.0.1:${server.address().port}`,browser=await chromium.launch();
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],failed=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.url().includes('/api/dashboard/')&&r.status()>=400)failed.push(r.url());});
 await page.goto(base+'/#/review/issues/TAP-029');
 await expect(page.getByText('Cases to cover',{exact:true})).toBeVisible();
 await expect(page.getByText('Please include a scanned PDF as well; a text-only fixture will miss the OCR path.',{exact:true})).toBeVisible();
 await page.goto(base+'/#/review/issues/TAP-033');await expect(page.getByText('Decision needed',{exact:true})).toBeVisible();
 await page.goto(base+'/#/review/usage');
 await expect(page.getByText('Leaderboard',{exact:true})).toBeVisible();
 await expect(page.getByText('No usage yet',{exact:true})).toHaveCount(0);
 await expect(page.getByText('Daily tokens',{exact:true})).toBeVisible();
 for(const [button,title] of [['Cost','Daily cost'],['Time','Daily run time'],['Runs','Daily runs'],['Tokens','Daily tokens']]){await page.getByRole('group',{name:'Metric',exact:true}).getByRole('button',{name:button,exact:true}).click();await expect(page.getByText(title,{exact:true})).toBeVisible();}
 await page.getByRole('button',{name:'Period',exact:true}).click();
 const response=page.waitForResponse(r=>r.url().includes('/api/dashboard/usage/daily?')&&r.url().includes('days=7'));
 await page.getByRole('menuitemradio',{name:'7d',exact:true}).click();const seven=await (await response).json();assert.ok(seven.length>0);
 await expect(page.getByText('Cost · 7D',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Project',exact:true}).click();
 const projectResponse=page.waitForResponse(r=>r.url().includes('/api/dashboard/usage/daily?')&&r.url().includes('project_id='));
 await page.getByRole('menuitemradio',{name:'Developer Platform',exact:true}).click();const project=await (await projectResponse).json();
 const total=rows=>rows.reduce((n,r)=>n+r.task_count,0);assert.ok(total(project)>0&&total(project)<total(seven));
 await page.getByRole('tab',{name:'Errors',exact:true}).click();
 await expect(page.getByText('Daily errors',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Period',exact:true}).click();await page.getByRole('menuitemradio',{name:'90d',exact:true}).click();
 await expect(page.getByText('Failed runs · 90D',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Weekly',exact:true}).click();await expect(page.getByText('Weekly errors',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Period',exact:true}).click();await page.getByRole('menuitemradio',{name:'1d',exact:true}).click();await expect(page.getByText('Failed runs · 1D',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Project',exact:true}).click();await page.getByRole('menuitemradio',{name:'All projects',exact:true}).click();
 await page.getByRole('tab',{name:'Usage',exact:true}).click();await expect(page.getByText('Leaderboard',{exact:true})).toBeVisible();
 await page.screenshot({path:'/tmp/workpal-analytics-errors.png',fullPage:true});
 assert.deepEqual(errors,[]);assert.deepEqual(failed,[]);
 console.log('PASS: ticket rich text and discussion; Analytics charts, 7d/90d ranges, project filtering and Errors tab; no page exceptions');
}finally{await browser.close();await new Promise(r=>{server.close(r);server.closeAllConnections();});}
