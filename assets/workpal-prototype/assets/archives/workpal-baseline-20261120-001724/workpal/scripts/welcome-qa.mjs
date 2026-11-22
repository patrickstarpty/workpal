import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';

const require=createRequire(import.meta.url);
const {chromium,expect}=require(process.env.WORKPAL_PLAYWRIGHT||'@playwright/test');
const url=pathToFileURL(resolve('dist/Workpal.html')).href;
const browser=await chromium.launch();
try{
  for(const width of [1440,390]){
    // Use fresh documents: same-document hash navigation is intentionally direct.
    for(const target of ['#tasks','#agents?id=Engineering%20partner','#w/missing/tasks','#unknown']){
      const fresh=await browser.newPage({viewport:{width,height:900}});
      await fresh.goto(url+target);
      await expect(fresh.locator('.welcome-page')).toBeVisible();
      await expect(fresh.locator('.shell')).toHaveCount(0);
      const destination=target==='#unknown'||target.startsWith('#w/missing')?'#tasks':target;
      const open=fresh.getByRole('link',{name:'Enter workspace',exact:true});
      await expect(open).toHaveAttribute('href',destination);
      await fresh.reload();await expect(fresh.locator('.welcome-page')).toBeVisible();
      await expect(open).toHaveAttribute('href',destination);
      await open.click();await expect(fresh.locator('.shell')).toBeVisible();
      expect(new URL(fresh.url()).hash).toBe(destination);
      await fresh.close();
    }
    const context=await browser.newContext({viewport:{width,height:900}});
    await context.addInitScript(()=>{
      const schedule=window.setInterval;
      window.setInterval=(callback,delay,...args)=>{
        if(delay===15000)window.__welcomeTick=()=>callback(...args);
        return schedule(callback,delay,...args);
      };
    });
    const page=await context.newPage(),errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    const welcome=page.locator('.welcome-page'),enter=page.getByRole('link',{name:'Enter workspace',exact:true});
    await page.goto(url);
    await expect(welcome).toBeVisible();await expect(page).toHaveTitle('Welcome · Workpal');
    await expect(page).toHaveURL(/#welcome$/);await expect(page.locator('input')).toHaveCount(0);
    await expect(welcome.getByRole('heading',{name:'Workpal',exact:true})).toBeVisible();
    await expect(welcome.locator('h1 .brand-wordmark text')).toHaveText('Workpal');
    await expect(welcome.locator('h1')).toHaveCSS('font-style','italic');
    await expect(welcome.locator('h1')).toHaveCSS('font-family',/Inter/);
    await expect(welcome.locator('.welcome-brand-mark')).toHaveCount(1);
    await expect(welcome.locator('.welcome-brand-mark')).toHaveAttribute('aria-hidden','true');
    await expect(welcome.locator('.welcome-slogan')).toHaveText('Let’s work together.');
    await expect(welcome.locator('.welcome-description,.welcome-note')).toHaveCount(0);
    await expect(welcome).not.toContainText(/sign.in|log.in|open workspace/i);
    await expect(enter).toHaveText('Enter workspace');await expect(enter.locator('svg')).toBeVisible();
    await page.reload();await expect(welcome).toBeVisible();
    await page.dispatchEvent('body','keydown',{key:'j',ctrlKey:true});
    await page.dispatchEvent('body','keydown',{key:'k',ctrlKey:true});
    await expect(page.locator('#assistant')).toHaveCount(0);await expect(page.locator('#dialog')).not.toBeVisible();
    const scheduleBlocked=await page.evaluate(()=>{
      const db=WorkpalStudio.db,old=db.autopilots,trigger=WorkpalStudio.triggerAutopilot;
      let calls=0;
      db.autopilots=[{id:'WELCOME-CHECK',enabled:true,time:new Date().toTimeString().slice(0,5),lastDay:''}];
      WorkpalStudio.triggerAutopilot=()=>{calls++;};
      window.__welcomeTick();
      const blocked=calls===0&&db.autopilots[0].lastDay==='';
      db.autopilots=old;WorkpalStudio.triggerAutopilot=trigger;
      return blocked;
    });
    expect(scheduleBlocked).toBe(true);await expect(welcome).toBeVisible();
    await enter.focus();await page.keyboard.press('Enter');await expect(page).toHaveURL(/#tasks$/);
    await expect(page.locator('.shell')).toBeVisible();
    await page.goBack();await expect(welcome).toBeVisible();
    await page.goForward();await expect(page.locator('.shell')).toBeVisible();
    await page.reload();await expect(welcome).toBeVisible();
    await expect(enter).toHaveAttribute('href','#tasks');
    await enter.click();await expect(page.locator('.shell')).toBeVisible();

    // Saved notes, selected theme and an unsaved issue survive a visit home.
    await page.goto(url+'#settings');await expect(welcome).toHaveCount(0);
    await page.getByLabel('Theme',{exact:true}).selectOption('neutral');
    await page.getByRole('button',{name:'Workspace notes',exact:true}).click();
    const dialog=page.locator('#dialog');
    await dialog.locator('[name=author]').fill('Welcome reviewer');
    await dialog.locator('[name=text]').fill('Keep welcome review note '+width);
    await dialog.getByRole('button',{name:'Save feedback',exact:true}).click();await page.keyboard.press('Escape');
    await page.goto(url+'#tasks');await page.locator('.top').getByRole('button',{name:'New issue',exact:true}).click();
    await dialog.locator('[name=title]').fill('Keep welcome issue draft '+width);
    await page.evaluate(()=>{location.hash='welcome';});await expect(welcome).toBeVisible();
    await expect(dialog).not.toBeVisible();await expect(page.locator('html')).toHaveAttribute('data-theme','neutral');
    await enter.click();await page.locator('.top').getByRole('button',{name:'New issue',exact:true}).click();
    await expect(dialog.locator('[name=title]')).toHaveValue('Keep welcome issue draft '+width);await page.keyboard.press('Escape');
    await page.goto(url+'#settings');await page.getByRole('button',{name:'Workspace notes',exact:true}).click();
    await expect(dialog).toContainText('Keep welcome review note '+width);await page.keyboard.press('Escape');

    const space=await page.evaluate(()=>WorkpalStudio.createWorkspace('Welcome team'));
    await page.goto(url+'#w/'+space+'/overview');await expect(page.locator('.shell')).toBeVisible();
    await page.reload();await expect(welcome).toBeVisible();
    await expect(enter).toHaveAttribute('href','#w/'+space+'/overview');
    await enter.click();await expect(page.locator('.shell')).toBeVisible();
    if(width>=768)await page.getByRole('link',{name:'Workpal home',exact:true}).click();
    else await page.evaluate(()=>{location.hash='welcome';});
    await expect(welcome).toBeVisible();await expect(enter).toHaveAttribute('href','#w/'+space+'/overview');
    await enter.click();await expect(page).toHaveURL(new RegExp('#w/'+space+'/overview$'));
    await page.goto(url+'#agents');await expect(page.locator('.agent-table')).toBeVisible();
    await page.goto(url+'#welcome');
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    expect(errors).toEqual([]);
    console.log('PASS welcome '+width+'px: welcome-first startup/reload/bookmarks, pending target/fallback, keyboard/history, in-app routes, last workspace, notes/theme/draft, shortcut and timer isolation.');
    await context.close();
  }
}finally{await browser.close();}
