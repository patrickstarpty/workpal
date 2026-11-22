import assert from 'node:assert/strict';
import {chromium,expect} from '@playwright/test';
const base=process.env.WORKPAL_QA_URL||'http://127.0.0.1:4174';
const browser=await chromium.launch();
try {
 const page=await browser.newPage();const errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base);
 const login=async()=>{await expect(page.getByLabel('Email',{exact:true})).toHaveValue('workpal@fwd.com');await expect(page.getByRole('button',{name:'Sign in',exact:true})).toBeEnabled();await page.getByRole('button',{name:'Sign in',exact:true}).click();await expect(page.getByRole('button',{name:'Enter Workspace',exact:true})).toBeVisible();};
 await login();await page.reload();await login();
 await page.getByRole('button',{name:'Enter Workspace',exact:true}).click();await expect(page).toHaveURL(/review\/issues/);
 const headers={'X-Workspace-Slug':'review'};
 for(const path of ['projects','issues','agents','skills','squads','autopilots','labels','runtimes','chat/sessions','inbox','inbox/snoozed','dashboard/usage/daily?days=90','dashboard/contribution?days=30']){
  const r=await page.request.get(base+'/api/'+path,{headers});assert.equal(r.status(),200,path);
  const data=await r.json();console.log(path,Array.isArray(data)?data.length:(data.total??data.projects?.length??Object.keys(data).join(',')));
 }
 for(const route of ['projects','issues','agents','skills','squads','autopilots','runtimes','usage']){
  await page.evaluate(route=>{location.hash='/review/'+route;},route);
  await page.waitForTimeout(800);
  assert.equal(await page.locator('[data-page-error]').count(),0,route);
  if(route==='runtimes')await expect(page.getByText('Copilot CLI',{exact:true})).toHaveCount(4,{timeout:20000});
  if(route==='agents')for(const agent of await (await page.request.get(base+'/api/agents',{headers})).json())await expect(page.getByText(agent.name,{exact:true}).first()).toBeVisible();
  console.log('PAGE',route,(await page.locator('body').innerText()).slice(-220).replaceAll('\n',' | '));
 }
 const squads=await (await page.request.get(base+'/api/squads',{headers})).json();
 await page.evaluate(()=>{location.hash='/review/squads';});
 for(const squad of squads)await expect(page.getByText(squad.name,{exact:true}).first()).toBeVisible();
 await page.reload();await expect(page.getByRole('button',{name:'Sign in',exact:true})).toBeVisible();
 assert.deepEqual(errors,[]);console.log('PASS login on reload, all collection APIs, page rendering and squads');
}finally{await browser.close();}
