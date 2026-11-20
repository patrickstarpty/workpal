import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.WORKPAL_PLAYWRIGHT||'@playwright/test');
const base=process.env.WORKPAL_URL||'http://127.0.0.1:4174';
const browser=await chromium.launch();
let project;
try {
 const page=await browser.newPage({viewport:{width:1440,height:900}});const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 const response=await fetch(base+'/api/projects',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({title:'QA persistence'})});assert.equal(response.status,201);project=await response.json();
 await page.goto(`${base}/#/review/projects/${project.id}`);
 const title=page.getByRole('textbox',{name:'Project title'});await title.fill('Saved through frontend');
 const saved=page.waitForResponse(r=>r.url().endsWith('/api/projects/'+project.id)&&r.request().method()==='PUT');await title.press('Tab');assert.equal((await saved).status(),200);
 await page.reload();await title.waitFor();assert.equal(await title.innerText(),'Saved through frontend');
 for(const width of [1440,390]){
  await page.setViewportSize({width,height:900});
  for(const route of ['projects','issues','agents','skills','squads','autopilots','inbox','chat','settings','dashboard']){
   await page.goto(`${base}/#/review/${route}`);await page.waitForTimeout(700);
   assert.equal(await page.locator('#reference-error').count(),0,route);
   assert.ok(!(await page.locator('body').innerText()).includes("Couldn't load the status list"),route);
  }
 }
 assert.deepEqual(errors,[]);console.log('PASS: 20 page loads, project UI edit and reload persistence');
}finally{if(project)await fetch(base+'/api/projects/'+project.id,{method:'DELETE'});await browser.close();}
