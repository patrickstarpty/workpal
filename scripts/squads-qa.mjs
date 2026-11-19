import {gotoWorkspace,reloadWorkspace} from './qa-navigation.mjs';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';
import {mkdir} from 'node:fs/promises';

const require=createRequire(import.meta.url);
const {chromium,expect}=require(process.env.WORKPAL_PLAYWRIGHT||'@playwright/test');
const url=pathToFileURL(resolve('dist/Workpal.html')).href;
const browser=await chromium.launch();
await mkdir('test-results',{recursive:true});
const failures=[];
try {
  for(const width of [1440,390]){
    const context=await browser.newContext({viewport:{width,height:900}});
    const page=await context.newPage();
    page.setDefaultTimeout(8000);
    const errors=[],remoteRequests=[];
    page.on('pageerror',error=>errors.push(error.message));
    page.on('request',request=>{if(/^https?:/.test(request.url()))remoteRequests.push(request.url());});
    const squadUrl=url+'#squads?id='+encodeURIComponent('TAP delivery');
    const dialog=page.locator('#dialog');
    const avatarButton=()=>page.getByRole('button',{name:'Change avatar for Engineering partner',exact:true});
    async function noOverflow(){
      expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
      const target=await dialog.isVisible()?dialog:page.locator('main');
      expect(await target.evaluate(el=>el.scrollWidth-el.clientWidth)).toBeLessThanOrEqual(1);
    }
    try {
      // Save a reviewer note before changing assignments and shared identities.
      await gotoWorkspace(page,url+'#settings');
      await page.getByRole('button',{name:'Workspace notes',exact:true}).click();
      await dialog.locator('[name=author]').fill('Squad reviewer');
      await dialog.locator('[name=text]').fill('Keep the squad review note '+width);
      await dialog.getByRole('button',{name:'Save feedback',exact:true}).click();
      await page.keyboard.press('Escape');
      await gotoWorkspace(page,squadUrl);
      const baseline=await page.evaluate(()=>({tasks:WorkpalStudio.db.tasks.length,runs:WorkpalStudio.db.runs.length}));
      const assign=page.locator('main .heading').getByRole('button',{name:'Assign work',exact:true});
      await expect(assign).toBeVisible();
      await assign.focus();
      await page.keyboard.press('Enter');
      const form=dialog.locator('form[data-form=assignWork]');
      await expect(form).toBeVisible();
      await expect(form.locator('.assignment-owner')).toHaveText('TAP delivery');
      await expect(form.locator('[name=owner]')).toHaveCount(0);
      await expect(form.locator('[name=queueRun]')).toBeChecked();
      await expect(form).toContainText('Engineering partner is the coordination lead');
      await expect(form).toContainText('Runtime offline');
      await noOverflow();
      await page.screenshot({path:'test-results/squad-assignment-'+width+'.png'});
      await page.keyboard.press('Escape');
      await expect(dialog).not.toBeVisible();
      expect(await page.evaluate(()=>WorkpalStudio.db.tasks.length)).toBe(baseline.tasks);
      await assign.click();
      await form.locator('[name=title]').fill('Coordinate upload delivery '+width);
      await form.locator('[name=description]').fill('Keep the squad as assignee and capture its coordination context.');
      await form.locator('.assignment-criteria > summary').click();
      await form.locator('[name=checks]').fill('Preserve squad ownership\nRecord the leader and member responsibilities');
      await form.locator('[name=priority]').selectOption('High');
      await form.locator('[name=project]').selectOption('TAP');
      await form.getByRole('button',{name:'Create issue',exact:true}).click();
      const created=await page.evaluate(title=>{
        const task=WorkpalStudio.db.tasks.find(t=>t.title===title);
        return {task,runs:WorkpalStudio.db.runs.filter(r=>r.task===task?.id)};
      },'Coordinate upload delivery '+width);
      expect(created.task.owner).toBe('TAP delivery');
      expect(created.task.status).toBe('todo');
      expect(created.task.checks).toHaveLength(2);
      expect(created.runs).toHaveLength(1);
      expect(created.runs[0].agent).toBe('Engineering partner');
      expect(created.runs[0].status).toBe('queued');
      expect(created.runs[0].context.squad.name).toBe('TAP delivery');
      expect(created.runs[0].context.squad.members).toContain('Quality partner');
      expect(created.runs[0].context.squad.instructions).toContain('Delegate implementation');
      await reloadWorkspace(page);
      expect(await page.evaluate(id=>WorkpalStudio.db.runs.filter(r=>r.task===id).length,created.task.id)).toBe(1);
      await gotoWorkspace(page,squadUrl);
      await expect(page.locator('main')).toContainText('Coordinate upload delivery '+width);

      // A parked issue and an explicit no-run assignment must not enqueue work.
      for(const mode of ['unchecked','backlog']){
        await page.locator('main .heading').getByRole('button',{name:'Assign work',exact:true}).click();
        await form.locator('[name=title]').fill(mode+' squad assignment '+width);
        if(mode==='unchecked')await form.locator('[name=queueRun]').uncheck();
        else {
          await form.locator('[name=status]').selectOption('backlog');
          await expect(form.locator('[name=queueRun]')).not.toBeChecked();
          await expect(form.locator('[name=queueRun]')).toBeDisabled();
        }
        await form.getByRole('button',{name:'Create issue',exact:true}).click();
        const result=await page.evaluate(title=>{
          const task=WorkpalStudio.db.tasks.find(t=>t.title===title);
          return {owner:task.owner,status:task.status,runs:WorkpalStudio.db.runs.filter(r=>r.task===task.id).length};
        },mode+' squad assignment '+width);
        expect(result.owner).toBe('TAP delivery');
        expect(result.status).toBe(mode==='backlog'?'backlog':'todo');
        expect(result.runs).toBe(0);
        await gotoWorkspace(page,squadUrl);
      }

      // Avatar choices belong to the agent, so every surface uses one identity.
      await avatarButton().click();
      await expect(dialog.locator('form[data-form=avatarEditor]')).toBeVisible();
      await dialog.getByRole('button',{name:'Use 🚀',exact:true}).click();
      await expect(dialog.getByRole('button',{name:'Use 🚀',exact:true})).toHaveAttribute('aria-pressed','true');
      await expect(dialog.locator('[name=emoji]')).toHaveValue('🚀');
      await noOverflow();
      await page.screenshot({path:'test-results/squad-avatar-picker-'+width+'.png'});
      await dialog.getByRole('button',{name:'Save avatar',exact:true}).click();
      await expect(avatarButton().locator('.avatar')).toHaveText('🚀');
      await reloadWorkspace(page);
      await expect(avatarButton().locator('.avatar')).toHaveText('🚀');
      await gotoWorkspace(page,url+'#agents');
      await expect(page.getByRole('button',{name:'Change avatar for Engineering partner',exact:true}).locator('.avatar')).toHaveText('🚀');
      const taskId=await page.evaluate(()=>WorkpalStudio.db.tasks.find(t=>t.owner==='Engineering partner').id);
      await gotoWorkspace(page,url+'#tasks');
      await expect(page.locator('button[data-id="issue|'+taskId+'"] .avatar')).toHaveText('🚀');
      await gotoWorkspace(page,squadUrl);
      await avatarButton().click();
      const family='👩‍👩‍👧‍👦';
      await dialog.locator('[name=emoji]').fill(family);
      await dialog.getByRole('button',{name:'Save avatar',exact:true}).click();
      await expect(avatarButton().locator('.avatar')).toHaveText(family);
      await avatarButton().click();
      await dialog.locator('[name=emoji]').fill('<img src=x onerror=alert(1)>');
      await dialog.getByRole('button',{name:'Save avatar',exact:true}).click();
      await expect(dialog).toBeVisible();
      await expect(page.locator('#toast')).toContainText('Choose or paste one emoji');
      await expect(page.locator('img[src=x]')).toHaveCount(0);
      expect(await page.evaluate(()=>WorkpalStudio.db.agents.find(a=>a.name==='Engineering partner').emoji)).toBe(family);
      await dialog.getByRole('button',{name:'Use default avatar',exact:true}).click();
      await expect(dialog.locator('[name=emoji]')).toHaveValue('');
      await dialog.getByRole('button',{name:'Save avatar',exact:true}).click();
      await expect(avatarButton().locator('.avatar svg')).toHaveCount(1);
      await reloadWorkspace(page);
      await expect(avatarButton().locator('.avatar svg')).toHaveCount(1);
      await noOverflow();

      await gotoWorkspace(page,url+'#settings');
      await page.getByRole('button',{name:'Workspace notes',exact:true}).click();
      await expect(dialog).toContainText('Keep the squad review note '+width);
      await page.keyboard.press('Escape');
      await expect(dialog).not.toBeVisible();
      expect(errors).toEqual([]);
      expect(remoteRequests).toEqual([]);
      console.log('PASS squads '+width+'px: header assignment, routing/context, no-run options, emoji propagation/reset, text safety, notes, keyboard and layout');
    }catch(error){
      failures.push(width+'px: '+error.stack);
      await page.screenshot({path:'test-results/squads-failure-'+width+'.png'});
    }finally{
      await context.close();
    }
  }
}finally{
  await browser.close();
}
if(failures.length)throw Error(failures.join('\n\n'));
console.log('Squads browser QA passed at desktop and narrow widths.');
