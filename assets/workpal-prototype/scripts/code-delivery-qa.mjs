import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';
const require=createRequire(import.meta.url),{chromium,expect}=require(process.env.WORKPAL_PLAYWRIGHT||'@playwright/test');
const browser=await chromium.launch();
try{for(const width of [1440,390]){
 const page=await browser.newPage({viewport:{width,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(pathToFileURL(resolve('dist/Workpal.html')).href);await page.locator('.welcome-enter').click();
 await page.evaluate(()=>location.hash='#runtimes');await page.getByRole('button',{name:'Register runtime',exact:true}).click();
 const runtime=page.locator('form[data-form=runtimeEditor]');await runtime.locator('[name=name]').fill('Review Mac');await runtime.locator('[name=directory]').fill('/Users/patrick/Desktop/Workspace/ai-native/workpal');await expect(runtime.locator('[name=readAccess]')).toHaveValue('Not checked');await runtime.getByRole('button',{name:'Save runtime',exact:true}).click();
 await page.evaluate(()=>location.hash='#projects');await page.locator('main [data-id="project|TAP"]').first().click();
 await page.getByRole('button',{name:'Manage resources',exact:true}).click();
 let form=page.locator('form[data-form="resourceEditor"]');await form.locator('[name=name]').fill('Code <safe>');await form.locator('[name=url]').fill('https://github.com/acme/code');await form.getByRole('button',{name:'Save resource',exact:true}).click();
 await page.getByRole('button',{name:'Manage resources',exact:true}).click();form=page.locator('form[data-form="resourceEditor"]');await form.locator('[name=resourceId]').selectOption({label:'Code <safe>'});await expect(form.locator('[name=url]')).toHaveValue('https://github.com/acme/code');await form.locator('[name=startingRef]').fill('develop');await form.getByRole('button',{name:'Save resource',exact:true}).click();
 await page.getByRole('button',{name:'Manage resources',exact:true}).click();form=page.locator('form[data-form=resourceEditor]');await form.locator('[name=resourceId]').selectOption('');await form.locator('[name=kind]').selectOption('folder');await form.locator('[name=name]').fill('Workpal local');await form.locator('[name=runtimeId]').selectOption({label:'Review Mac'});await form.locator('[name=path]').fill('/Users/patrick/Desktop/Workspace/ai-native/workpal');await form.getByRole('button',{name:'Save resource',exact:true}).click();
 await page.getByRole('button',{name:'Edit delivery rules',exact:true}).click();form=page.locator('form[data-form="deliveryRules"]');await form.locator('[name=completion]').selectOption('merged');await form.getByRole('button',{name:'Save delivery rules',exact:true}).click();
 await page.getByRole('button',{name:'Edit project',exact:true}).click();await page.locator('form[data-form=projectConfig]').getByRole('button',{name:'Save project',exact:true}).click();
 expect(await page.evaluate(()=>WorkpalStudio.db.projectSettings.find(p=>p.project==='TAP').resources[0].startingRef)).toBe('develop');
 const id=await page.evaluate(()=>{const s=WorkpalStudio,t=s.assignWork('Engineering partner',{title:'Code delivery QA',project:'TAP',checks:['Verified'],status:'todo',queueRun:false}).task;s.start(t,'brainstorming');return t.id;});
 await page.evaluate(id=>location.hash='#tasks?id='+id,id);await page.getByRole('button',{name:'Link PR',exact:true}).click();form=page.locator('form[data-form=pullRequest]');await form.locator('[name=url]').fill('https://github.com/acme/code/pull/1');await form.locator('[name=source]').fill('workpal/test');await form.locator('[name=sha]').fill('abcdef1');await form.getByRole('button',{name:'Save PR record',exact:true}).click();await expect(page.getByText('Manual record ·',{exact:false})).toBeVisible();
 await page.evaluate(()=>location.hash='#settings');await page.getByRole('button',{name:'Configure Code',exact:true}).click();await page.locator('form[data-form=codeSettings] [name=afterMerge]').selectOption('complete');await page.getByRole('button',{name:'Save Code settings',exact:true}).click();
 await page.evaluate(id=>{const s=WorkpalStudio,r=s.db.runs.find(r=>r.task===id);s.changeRun(r,'deliver','Ready',{artifacts:[{title:'Patch',body:'Observed patch'}],evidence:[{criterion:'Verified',evidence:'Checked',status:'supported'}]});s.decide(r.id,r.stage,'approve','Accepted',{acknowledged:true});location.hash='#tasks?id='+id;},id);
 await page.getByRole('button',{name:'Update',exact:true}).click();await page.locator('form[data-form=pullRequest] [name=state]').selectOption('merged');await page.getByRole('button',{name:'Save PR record',exact:true}).click();expect(await page.evaluate(id=>WorkpalStudio.db.tasks.find(t=>t.id===id).status,id)).toBe('done');
 await page.reload();expect(await page.evaluate(id=>WorkpalStudio.db.tasks.find(t=>t.id===id).status,id)).toBe('done');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);expect(errors).toEqual([]);await page.close();
}console.log('Code delivery QA passed at 1440px and 390px.');}finally{await browser.close();}
