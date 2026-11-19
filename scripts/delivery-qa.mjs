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
    // Fresh ephemeral browser storage keeps test records away from reviewer notes.
    const context=await browser.newContext({viewport:{width,height:900},acceptDownloads:true});
    const page=await context.newPage();
    page.setDefaultTimeout(8000);
    const errors=[];
    const remoteRequests=[];
    page.on('request',request=>{if(/^https?:/.test(request.url()))remoteRequests.push(request.url());});
    page.on('pageerror',error=>errors.push(error.message));
    try {
      await gotoWorkspace(page,url+'#projects?id=TAP');
      const editor=page.locator('#dialog');
      await page.locator('main').getByRole('button',{name:/New issue/}).click();
      const title='Verify upload recovery '+width;
      await editor.locator('[name=title]').fill(title);
      await editor.locator('[name=description]').fill('Keep the upload and its progress after reconnect.');
      await editor.locator('[name=status]').selectOption('backlog');
      await editor.locator('[name=owner]').selectOption('Engineering partner');
      await editor.locator('[name=checks]').fill('Retain progress on reconnect\nAllow retry after timeout');
      await editor.getByRole('button',{name:'Create issue',exact:true}).click();
      const issueUrl=page.url();
      const issueId=await page.evaluate(title=>WorkpalStudio.db.tasks.find(t=>t.title===title).id,title);
      await page.locator('main').getByRole('button',{name:'Start run',exact:true}).click();
      await editor.locator('[name=skill]').selectOption('webapp-testing');
      await expect(editor).toContainText(/offline/i);
      await editor.getByRole('button',{name:'Start workflow',exact:true}).click();
      const firstRunUrl=page.url();
      await expect(page.locator('main')).toContainText(/Runtime offline/i);
      await expect(page.locator('main')).toContainText('Retain progress on reconnect');
      await page.locator('form[data-form=deliver] [name=note]').fill('First delivery: upload state retained; retry evidence missing.');
      await page.locator('[name=artifactTitle]').fill('Upload recovery notes');
      await page.locator('[name=artifactBody]').fill('Manual review reference: retain file and progress while disconnected.');
      await page.locator('[name=evidence0]').fill('Manual reference documents retained progress after reconnect.');
      await page.getByRole('button',{name:'Submit for review',exact:true}).click();
      const firstDelivery=await page.evaluate(id=>WorkpalStudio.latestDelivery(id),issueId);
      expect(firstDelivery.version).toBe(1);
      await expect(page.locator('main')).toContainText(/missing|evidence required|incomplete/i);
      await expect(page.locator('[name=choice]')).toHaveValue('return');
      await page.locator('form[data-form=decision] [name=note]').fill('Add evidence for retry after timeout.');
      await page.getByRole('button',{name:'Record decision',exact:true}).click();
      await page.getByRole('button',{name:'Start another attempt',exact:true}).click();
      await editor.getByRole('button',{name:'Start workflow',exact:true}).click();
      const secondRunUrl=page.url();
      const unsafe='<img src=x onerror="globalThis.deliveryInjection=true">';
      await page.locator('form[data-form=deliver] [name=note]').fill('Second delivery: adds timeout retry evidence.');
      await page.locator('[name=artifactTitle]').fill('Upload recovery checklist');
      await page.locator('[name=artifactBody]').fill('Reviewer-authored checklist. Literal input: '+unsafe);
      await page.locator('[name=evidence0]').fill('Checklist item 1: preserve file and progress across reconnect.');
      await page.locator('[name=evidence1]').fill('Checklist item 2: retry timeout from the retained offset.');
      await page.locator('[name=limitations]').fill('No code or tests have been run in this offline walkthrough.');
      await page.getByRole('button',{name:'Submit for review',exact:true}).click();
      const secondDelivery=await page.evaluate(id=>WorkpalStudio.latestDelivery(id),issueId);
      expect(secondDelivery.version).toBe(2);
      expect(secondDelivery.supersedes).toBe(firstDelivery.id);
      await expect(page.locator('main')).toContainText('Second delivery: adds timeout retry evidence.');
      await page.locator('.delivery-comparison > summary').click();
      await expect(page.locator('.delivery-comparison')).toContainText('First delivery: upload state retained; retry evidence missing.');
      await expect(page.locator('.delivery-comparison')).toContainText('Second delivery: adds timeout retry evidence.');
      expect(await page.evaluate(()=>globalThis.deliveryInjection)).toBeUndefined();
      await expect(page.locator('main img[src=x]')).toHaveCount(0);
      expect(await page.locator('main').evaluate(el=>el.scrollWidth-el.clientWidth)).toBeLessThanOrEqual(1);
      expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
      await page.screenshot({path:'test-results/delivery-review-'+width+'.png'});
      await gotoWorkspace(page,firstRunUrl);
      await expect(page.locator('main')).toContainText('First delivery: upload state retained; retry evidence missing.');
      await expect(page.locator('form[data-form=decision]')).toHaveCount(0);
      await gotoWorkspace(page,secondRunUrl);
      await page.locator('[name=choice]').selectOption('approve');
      await page.locator('[name=acknowledged]').check();
      await page.getByRole('button',{name:'Record decision',exact:true}).click();
      await reloadWorkspace(page);
      expect(await page.evaluate(id=>WorkpalStudio.db.tasks.find(t=>t.id===id).status,issueId)).toBe('done');
      await expect(page.locator('form[data-form=decision]')).toHaveCount(0);
      await gotoWorkspace(page,issueUrl);
      await expect(page.locator('main')).toContainText('Add evidence for retry after timeout.');
      await expect(page.locator('main')).toContainText('Second delivery: adds timeout retry evidence.');

      // Editing the issue later must not rewrite the original execution report.
      await page.getByRole('button',{name:'Edit issue',exact:true}).click();
      await editor.locator('[name=title]').fill('Changed requirements '+width);
      await editor.locator('[name=checks]').fill('New acceptance condition');
      await editor.getByRole('button',{name:'Save changes',exact:true}).click();
      await gotoWorkspace(page,secondRunUrl);
      await page.getByRole('button',{name:'Generate execution report',exact:true}).click();
      await editor.getByRole('button',{name:'Generate execution report',exact:true}).click();
      const report=await page.evaluate(()=>WorkpalStudio.db.reports[0]);
      expect(report.body).toContain(title);
      expect(report.body).toContain('Retain progress on reconnect');
      expect(report.body).not.toContain('New acceptance condition');
      expect(report.body).toMatch(/offline|no agent/i);
      const download=page.waitForEvent('download');
      await page.getByRole('button',{name:'Export Markdown',exact:true}).click();
      expect((await download).suggestedFilename()).toMatch(/\.md$/);

      // Existing local review notes remain usable and escaped through reload.
      await gotoWorkspace(page,url+'#settings');
      await page.getByRole('button',{name:'Workspace notes',exact:true}).click();
      await editor.locator('[name=author]').fill('Delivery reviewer');
      await editor.locator('[name=text]').fill('Keep this review note '+width+' '+unsafe);
      await editor.getByRole('button',{name:'Save feedback',exact:true}).click();
      await expect(editor).toContainText('Keep this review note '+width);
      await reloadWorkspace(page);
      await page.getByRole('button',{name:'Workspace notes',exact:true}).click();
      await expect(editor).toContainText('Keep this review note '+width);
      expect(await page.evaluate(()=>globalThis.deliveryInjection)).toBeUndefined();
      await page.keyboard.press('Escape');
      await expect(editor).not.toBeVisible();
      expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
      expect(errors).toEqual([]);
      expect(remoteRequests).toEqual([]);
      console.log('PASS delivery journey '+width+'px: evidence, return, v2, approval, history, text safety, notes, export');
    }catch(error){
      failures.push(width+'px: '+error.stack);
      await page.screenshot({path:'test-results/delivery-failure-'+width+'.png'});
    }finally{
      await context.close();
    }
  }
}finally{
  await browser.close();
}
if(failures.length)throw Error(failures.join('\n\n'));
console.log('Delivery browser QA passed at desktop and narrow widths.');
