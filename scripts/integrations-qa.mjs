import {createRequire} from 'node:module';
import {mkdir} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {gotoWorkspace,reloadWorkspace} from './qa-navigation.mjs';

const require=createRequire(import.meta.url);
const candidates=process.env.WORKPAL_PLAYWRIGHT
  ? [process.env.WORKPAL_PLAYWRIGHT]
  : ['@playwright/test','/tmp/tap-browser-mj_qfqun/node_modules/@playwright/test','../multica/node_modules/@playwright/test'];
let playwright;
for(const candidate of candidates){
  try{playwright=require(candidate);break;}catch(error){if(error.code!=='MODULE_NOT_FOUND')throw error;}
}
if(!playwright)throw Error('Playwright is unavailable. Set WORKPAL_PLAYWRIGHT to an installed @playwright/test package.');
const {chromium,expect}=playwright;
const url=pathToFileURL(resolve('dist/Workpal.html')).href;
const browser=await chromium.launch();
await mkdir('test-results',{recursive:true});

try{
  for(const width of [1440,390]){
    const context=await browser.newContext({viewport:{width,height:1000}});
    const externalRequests=[];
    await context.route(/^https?:/,route=>{externalRequests.push(route.request().url());return route.abort();});
    const page=await context.newPage(),errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    const dialog=page.locator('#dialog');
    const main=page.locator('main');
    const rows=()=>main.locator('.repository-row');
    const repoRow=url=>rows().filter({hasText:url});
    const accountRow=name=>main.locator('.integration-account').filter({hasText:name});
    const route=async(hash)=>{
      await page.evaluate(hash=>{location.hash=hash;},hash);
      await expect(page).toHaveURL(new RegExp(hash.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')+'$'));
      await expect(dialog).not.toBeVisible();
    };
    const noOverflow=async()=>{
      expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    };
    const openRepository=async()=>{
      const add=main.locator('.repository-add-menu > summary');
      if(!await main.locator('.repository-add-menu').evaluate(el=>el.open)){
        await add.focus();await page.keyboard.press('Enter');
      }
      await main.getByRole('button',{name:/^Enter a URL/}).click();
      const form=dialog.locator('form[data-form="repositoryEditor"]');
      await expect(form).toBeVisible();
      return form;
    };
    const openRepositoryActions=async(url)=>{
      const menu=repoRow(url).locator('details');
      if(!await menu.evaluate(el=>el.open))await menu.locator('summary').click();
    };
    const editRepository=async(url)=>{
      await openRepositoryActions(url);
      await repoRow(url).getByRole('button',{name:'Edit',exact:true}).click();
      return dialog.locator('form[data-form="repositoryEditor"]');
    };
    const openJira=async(scope)=>{
      await main.getByRole('button',{name:scope==='team'?'Connect team account':'Connect my account',exact:true}).click();
      await dialog.getByRole('textbox',{name:'Search apps',exact:true}).fill('Jira');
      await dialog.locator('[data-id="integrationSetup|jira~'+scope+'"]').click();
      const form=dialog.locator('form[data-form="integrationSetup"]');
      await expect(form).toBeVisible();
      return form;
    };

    await gotoWorkspace(page,url+'#settings');
    await main.getByRole('button',{name:'Workspace notes',exact:true}).click();
    const note='Preserve integration review '+width;
    await dialog.locator('[name=author]').fill('Integration reviewer');
    await dialog.locator('[name=text]').fill(note);
    await dialog.getByRole('button',{name:'Save feedback',exact:true}).click();
    await page.keyboard.press('Escape');
    const notesBefore=await page.evaluate(()=>JSON.stringify(WorkpalStudio.db.notes));

    await route('#settings?tab=code');
    for(const name of ['Code hosting','Repositories','Pull requests & issues']){
      await expect(main.getByRole('heading',{name,exact:true})).toBeVisible();
    }
    const initialCount=await rows().count();
    const repositoryURL='https://github.com/workpal-qa/integrations.git';
    const editedURL='git@github.com:workpal-qa/integrations.git';
    const unsafeDescription='<img src=x onerror="window.integrationInjected=true">';

    let form=await openRepository();
    await form.locator('[name=url]').fill(repositoryURL);
    await form.locator('[name=description]').fill(unsafeDescription);
    await form.getByRole('button',{name:'Save repository',exact:true}).click();
    await expect(dialog).not.toBeVisible();
    await expect(rows()).toHaveCount(initialCount+1);
    await expect(repoRow(repositoryURL)).toContainText(unsafeDescription);
    await expect(page.locator('img[src="x"]')).toHaveCount(0);
    expect(await page.evaluate(()=>window.integrationInjected)).toBeUndefined();

    // SSH and HTTPS must not create two entries for the same repository.
    form=await openRepository();
    await form.locator('[name=url]').fill(editedURL);
    await form.getByRole('button',{name:'Save repository',exact:true}).click();
    await expect(page.locator('#toast')).toContainText(/already (added|exists|in the workspace)/i);
    await expect(form).toBeVisible();
    await expect(rows()).toHaveCount(initialCount+1);
    await page.keyboard.press('Escape');
    await expect(dialog).not.toBeVisible();

    // Cancel and Escape discard edits; only an explicit save changes a row.
    form=await editRepository(repositoryURL);
    await form.locator('[name=url]').fill('https://github.com/workpal-qa/cancelled.git');
    await form.getByRole('button',{name:'Cancel',exact:true}).click();
    await expect(repoRow(repositoryURL)).toHaveCount(1);
    form=await editRepository(repositoryURL);
    await form.locator('[name=description]').fill('Unsaved change');
    await page.keyboard.press('Escape');
    await expect(dialog).not.toBeVisible();
    await expect(repoRow(repositoryURL)).toContainText(unsafeDescription);
    form=await editRepository(repositoryURL);
    await form.locator('[name=url]').fill(editedURL);
    await form.locator('[name=description]').fill('Repository used for integration review');
    await form.getByRole('button',{name:'Save repository',exact:true}).click();
    await expect(repoRow(editedURL)).toHaveCount(1);
    await reloadWorkspace(page);
    await expect(repoRow(editedURL)).toContainText('Repository used for integration review');
    await noOverflow();
    await page.screenshot({path:'test-results/integrations-code-'+width+'.png',fullPage:true});

    await route('#settings?tab=apps');
    for(const name of ['Team accounts','My accounts'])await expect(main.getByRole('heading',{name,exact:true})).toBeVisible();
    const teamName='Jira team <review '+width+'>';
    const personalName='Jira personal '+width;
    form=await openJira('team');
    await form.locator('[name=name]').fill(teamName);
    await form.getByRole('button',{name:'Save setup',exact:true}).click();
    await expect(accountRow(teamName)).toContainText('Authorization required');
    await expect(accountRow(teamName)).not.toContainText('Connected');
    await expect(accountRow(teamName)).toContainText(teamName);
    form=await openJira('personal');
    await form.locator('[name=name]').fill(personalName);
    await form.getByRole('button',{name:'Save setup',exact:true}).click();
    await expect(accountRow(personalName)).toContainText('Authorization required');
    await accountRow(teamName).getByRole('button',{name:'Edit setup',exact:true}).click();
    form=dialog.locator('form[data-form="integrationSetup"]');
    await expect(form.locator('[name=name]')).toHaveValue(teamName);
    await form.locator('[name=name]').fill(teamName+' updated');
    await form.getByRole('button',{name:'Save setup',exact:true}).click();
    await reloadWorkspace(page);
    await expect(accountRow(teamName+' updated')).toContainText('Authorization required');
    await expect(accountRow(personalName)).toHaveCount(1);
    await noOverflow();
    await page.screenshot({path:'test-results/integrations-apps-'+width+'.png',fullPage:true});

    // Account drafts and repositories belong to their workspace.
    const other=await page.evaluate(()=>WorkpalStudio.createWorkspace('Integration isolation'));
    await route('#w/'+other+'/settings?tab=code');
    await expect.poll(()=>page.evaluate(()=>WorkpalStudio.workspace.id)).toBe(other);
    await expect(rows()).toHaveCount(0);
    await route('#w/'+other+'/settings?tab=apps');
    await expect(main.locator('.integration-account')).toHaveCount(0);
    await route('#settings?tab=apps');
    await expect(accountRow(teamName+' updated')).toHaveCount(1);
    await expect(accountRow(personalName)).toHaveCount(1);

    await accountRow(personalName).getByRole('button',{name:'Remove setup',exact:true}).click();
    await expect(dialog).toBeVisible();
    await dialog.getByRole('button',{name:'Cancel',exact:true}).click();
    await expect(accountRow(personalName)).toHaveCount(1);
    await accountRow(personalName).getByRole('button',{name:'Remove setup',exact:true}).click();
    await dialog.getByRole('button',{name:'Remove setup',exact:true}).click();
    await expect(accountRow(personalName)).toHaveCount(0);
    await expect(accountRow(teamName+' updated')).toHaveCount(1);

    await route('#settings?tab=code');
    await main.getByRole('button',{name:'Connect GitHub',exact:true}).click();
    form=dialog.locator('form[data-form="integrationSetup"]');
    await form.locator('[name=name]').fill('GitHub QA organization');
    await form.getByRole('button',{name:'Save setup',exact:true}).click();
    await expect(accountRow('GitHub QA organization')).toContainText('Authorization required');
    await expect(accountRow('GitHub QA organization')).not.toContainText('Connected');

    await openRepositoryActions(editedURL);
    await repoRow(editedURL).getByRole('button',{name:'Delete repository',exact:true}).click();
    form=dialog.locator('form[data-form="repositoryRemove"]');
    await form.getByRole('button',{name:'Cancel',exact:true}).click();
    await expect(repoRow(editedURL)).toHaveCount(1);
    await openRepositoryActions(editedURL);
    await repoRow(editedURL).getByRole('button',{name:'Delete repository',exact:true}).click();
    await dialog.locator('form[data-form="repositoryRemove"]').getByRole('button',{name:'Delete repository',exact:true}).click();
    await expect(rows()).toHaveCount(initialCount);
    await reloadWorkspace(page);
    await expect(rows()).toHaveCount(initialCount);
    expect(await page.evaluate(()=>JSON.stringify(WorkpalStudio.db.notes))).toBe(notesBefore);
    await noOverflow();
    expect(errors).toEqual([]);
    expect(externalRequests).toEqual([]);
    console.log('PASS integrations '+width+'px: repository CRUD and duplicates, setup CRUD and authorization states, keyboard/cancel, escaping, reload, workspace isolation, preserved review notes, no external calls.');
    await context.close();
  }
}finally{await browser.close();}
