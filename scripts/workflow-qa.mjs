import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';
import {gotoWorkspace} from './qa-navigation.mjs';
const require=createRequire(import.meta.url);
let playwright;
for(const candidate of [process.env.WORKPAL_PLAYWRIGHT,'@playwright/test','/tmp/tap-browser-mj_qfqun/node_modules/@playwright/test','../multica/node_modules/@playwright/test'].filter(Boolean)){
  try{playwright=require(candidate);break;}catch(error){if(error.code!=='MODULE_NOT_FOUND')throw error;}
}
if(!playwright)throw Error('Set WORKPAL_PLAYWRIGHT to a local @playwright/test package.');
const {chromium,expect}=playwright,browser=await chromium.launch();
try{
  for(const width of [1440,768,390]){
    const context=await browser.newContext({viewport:{width,height:900}}),page=await context.newPage(),errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await gotoWorkspace(page,pathToFileURL(resolve('dist/Workpal.html')).href+'#tasks');
    await expect(page.locator('.issue-flow')).toHaveCount(0);
    await page.getByRole('button',{name:'Display',exact:true}).click();
    await page.getByRole('button',{name:'Board view',exact:true}).click();
    await expect(page.locator('.issue-flow')).toHaveCount(0);
    await page.evaluate(()=>{location.hash='#workflows';});
    const toggle=page.locator('[data-issue-flow-toggle]');
    await expect(toggle).toHaveAttribute('aria-expanded','true');
    await expect(page.locator('[data-issue-flow-node]')).toHaveCount(7);
    await expect(page.locator('.issue-flow-map')).toContainText('Restore to Done');
    const active=page.locator('[data-issue-flow-node=active]');
    await active.focus();await page.keyboard.press('Enter');
    await expect(page.locator('.issue-flow-detail')).toContainText('Finishing a run alone does not complete an issue');
    await page.keyboard.press('ArrowRight');await expect(page.locator('[data-issue-flow-node=review]')).toBeFocused();
    await page.keyboard.press('Space');await expect(page.locator('.issue-flow-detail')).toContainText('Request changes → In progress');
    await toggle.focus();await page.keyboard.press('Enter');await expect(page.locator('#issue-flow-content')).toBeHidden();
    await page.getByRole('button',{name:'New workflow',exact:true}).click();
    await expect(page.locator('#dialog form[data-form=workflowEditor]')).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(toggle).toHaveAttribute('aria-expanded','false');
    await toggle.click();
    await page.evaluate(()=>{
      const db=WorkpalStudio.db;db.projects.push('Flow QA');
      db.workflows.push({id:'flow-qa',name:'QA custom',steps:[{status:'review',next:'todo',rejected:'blocked',owner:'Project lead',instructions:'Verify the release.'}]});
      db.projectSettings.push({project:'Flow QA',lead:'Review owner',workflowId:'flow-qa'});
    });
    await toggle.click();await toggle.click();
    await page.getByRole('combobox',{name:'Workflow project'}).selectOption('Flow QA');
    await expect(page.locator('.issue-flow-detail')).toContainText('Approve → To do');
    await expect(page.locator('.issue-flow-detail')).toContainText('Request changes → Blocked');
    await expect(page.locator('.issue-flow-detail')).toContainText('Review owner');
    await page.evaluate(()=>{const db=WorkpalStudio.db;db.workflows.find(w=>w.id==='flow-qa').steps[0].next='done';db.projectSettings.find(p=>p.project==='Flow QA').deliveryRules={completion:'acceptance'};});
    await toggle.click();await toggle.click();
    await expect(page.locator('[data-issue-flow-node=gate]')).toHaveCount(1);
    await page.locator('[data-issue-flow-node=gate]').focus();await page.keyboard.press('Enter');
    await expect(page.locator('.issue-flow-detail')).toContainText('manual acceptance reason');
    await expect(page.locator('.issue-flow-detail')).toContainText('current delivery');
    expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    await expect(page.getByRole('button',{name:'New workflow',exact:true})).toBeVisible();
    await page.getByRole('button',{name:'QA custom',exact:true}).click();
    await expect(page.locator('#dialog form[data-form=workflowEditor]')).toBeVisible();
    await page.keyboard.press('Escape');
    expect(errors).toEqual([]);console.log(`${width}px: workflow routes, completion gate, keyboard, collapse, and bounds passed`);
    await context.close();
  }
}finally{await browser.close();}
