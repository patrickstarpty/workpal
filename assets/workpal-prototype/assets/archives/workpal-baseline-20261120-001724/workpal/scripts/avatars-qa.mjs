import {gotoWorkspace,reloadWorkspace} from './qa-navigation.mjs';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';

const require=createRequire(import.meta.url);
const {chromium,expect}=require(process.env.WORKPAL_PLAYWRIGHT||'@playwright/test');
const url=pathToFileURL(resolve('dist/Workpal.html')).href;
const browser=await chromium.launch();
try{
  for(const width of [1440,390]){
    const context=await browser.newContext({viewport:{width,height:900}});
    const page=await context.newPage();
    const errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    const dialog=page.locator('#dialog');
    const avatarButton=name=>page.getByRole('button',{name:'Change avatar for '+name,exact:true});
    const profile=name=>page.locator('.agent-row').filter({has:page.getByText(name,{exact:true})});
    const noOverflow=async()=>expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    await gotoWorkspace(page,url+'#settings');
    await page.getByRole('button',{name:'Workspace notes',exact:true}).click();
    await dialog.locator('[name=author]').fill('Avatar reviewer');
    await dialog.locator('[name=text]').fill('Keep avatar review note '+width);
    await dialog.getByRole('button',{name:'Save feedback',exact:true}).click();
    await page.keyboard.press('Escape');
    await gotoWorkspace(page,url+'#agents');
    const names=await page.evaluate(()=>WorkpalStudio.db.agents.map(agent=>agent.name));
    const choices=['🦊','🧠','🚀','🧪'];
    for(const [index,name] of names.entries()){
      const emoji=choices[index%choices.length];
      await avatarButton(name).focus();await page.keyboard.press('Enter');
      await expect(dialog).toBeVisible();
      await dialog.getByRole('button',{name:'Use '+emoji,exact:true}).click();
      await dialog.getByRole('button',{name:'Save avatar',exact:true}).click();
      await expect(page).toHaveURL(/#agents$/);
      await expect(avatarButton(name)).toBeFocused();
      await expect(avatarButton(name).locator('.avatar')).toHaveText(emoji);
      await reloadWorkspace(page);
      await expect(avatarButton(name).locator('.avatar')).toHaveText(emoji);
      await profile(name).click();
      await expect(page.locator('.agent-profile-avatar .avatar')).toHaveText(emoji);
      await noOverflow();
      await page.getByRole('button',{name:'New chat',exact:true}).click();
      await expect(page.locator('#assistant .chat-welcome .avatar')).toHaveText(emoji);
      await expect(page.locator('#assistant .compose-actions .avatar')).toHaveText(emoji);
      await page.getByRole('button',{name:'Close chat',exact:true}).click();
      await gotoWorkspace(page,url+'#agents');
    }
    // Creation and ordinary agent settings must also expose the same identity field.
    await page.getByRole('button',{name:'Configure agent',exact:true}).click();
    await dialog.locator('[name=name]').fill('Avatar specialist');
    await dialog.getByLabel('Emoji avatar',{exact:true}).fill('🦉');
    await dialog.locator('[name=role]').fill('Check emoji identities');
    await dialog.getByRole('button',{name:'Save agent',exact:true}).click();
    await expect(page.locator('.agent-profile-avatar .avatar')).toHaveText('🦉');
    await page.getByRole('button',{name:'Edit',exact:true}).click();
    await expect(dialog.getByLabel('Emoji avatar',{exact:true})).toHaveValue('🦉');
    const family='👩‍👩‍👧‍👦';
    await dialog.getByLabel('Emoji avatar',{exact:true}).fill(family);
    await dialog.getByRole('button',{name:'Save settings',exact:true}).click();
    await expect(page.locator('.agent-profile-avatar .avatar')).toHaveText(family);
    await reloadWorkspace(page);await expect(page.locator('.agent-profile-avatar .avatar')).toHaveText(family);
    await avatarButton('Avatar specialist').click();
    await dialog.getByLabel('Emoji',{exact:true}).fill('<img src=x onerror=alert(1)>');
    await dialog.getByRole('button',{name:'Save avatar',exact:true}).click();
    await expect(dialog).toBeVisible();await expect(page.locator('#toast')).toContainText('Choose or paste one emoji.');
    await expect(page.locator('img[src=x]')).toHaveCount(0);
    expect(await page.evaluate(()=>WorkpalStudio.db.agents.find(a=>a.name==='Avatar specialist').emoji)).toBe(family);
    await dialog.getByRole('button',{name:'Use default avatar',exact:true}).click();
    await dialog.getByRole('button',{name:'Save avatar',exact:true}).click();
    await expect(page.locator('.agent-profile-avatar .avatar svg')).toHaveCount(1);
    await reloadWorkspace(page);await expect(page.locator('.agent-profile-avatar .avatar svg')).toHaveCount(1);
    const squad=await page.evaluate(()=>WorkpalStudio.db.squads.find(s=>s.members.includes('Engineering partner'))?.name);
    if(squad){await gotoWorkspace(page,url+'#squads?id='+encodeURIComponent(squad));await expect(avatarButton('Engineering partner').locator('.avatar')).toHaveText(choices[names.indexOf('Engineering partner')%choices.length]);}
    const task=await page.evaluate(()=>WorkpalStudio.db.tasks.find(t=>t.owner==='Engineering partner')?.id);
    if(task){await gotoWorkspace(page,url+'#tasks');await expect(page.locator('button[data-id="issue|'+task+'"] .avatar')).toHaveText(choices[names.indexOf('Engineering partner')%choices.length]);}
    await gotoWorkspace(page,url+'#settings');await page.getByRole('button',{name:'Workspace notes',exact:true}).click();
    await expect(dialog).toContainText('Keep avatar review note '+width);
    await page.keyboard.press('Escape');await noOverflow();expect(errors).toEqual([]);
    console.log('PASS avatars '+width+'px: every seeded agent, creation/settings, persistence, shared list/profile/chat/squad/issue identity, reset, text safety, keyboard, review notes.');
    await context.close();
  }
}finally{await browser.close();}
