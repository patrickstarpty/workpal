import assert from 'node:assert/strict';
import {chromium,expect} from '@playwright/test';
const browser=await chromium.launch();const base='http://127.0.0.1:4174';
try{
 const page=await browser.newPage();await page.goto(base);await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page.getByRole('button',{name:'Enter Workspace',exact:true})).toBeVisible();
 let count=0;const urls=new Set();
 for(const slug of ['review','workpal-team']){
  const response=await page.request.get(base+'/api/agents',{headers:{'X-Workspace-Slug':slug}});assert.equal(response.status(),200);
  const agents=await response.json();
  for(const agent of agents){assert.match(agent.avatar_url,/^emoji:.+/u);urls.add(agent.avatar_url);count++;}
 }
 assert.equal(count,30);assert.equal(urls.size,15);

 await page.evaluate(()=>{location.hash='/home/team';});
 const marks=page.locator('[data-slot=avatar] [role=img]');await expect(marks.first()).toBeVisible();
 await expect(page.locator('img[src*="agent-avatars"]')).toHaveCount(0);
 await page.setViewportSize({width:390,height:844});
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
 await page.setViewportSize({width:1280,height:720});
 await page.getByRole('button',{name:'View Security Engineer role profile'}).first().click();
 await expect(page.locator('h1 [data-slot=avatar]')).toHaveText('🛡️');
 await page.evaluate(()=>{location.hash='/workpal-team/issues/workflow-work-10';});
 await expect(page.getByText('Requested outcome',{exact:true}).first()).toBeVisible();
 const avatar=page.getByRole('img',{name:'QA Engineer',exact:true}).first();await expect(avatar).toBeVisible();await expect(avatar).toHaveText('🧪');
 await page.evaluate(()=>{location.hash='/workpal-team/agents';});
 await expect(page.locator('[data-slot=avatar] [role=img]').first()).toBeVisible();
 await expect(page.locator('img[src^="emoji:"]')).toHaveCount(0);
 console.log('PASS: 30 agents, 15 native emoji avatars; team chart, profile, Activity and agent list');
}finally{await browser.close();}
