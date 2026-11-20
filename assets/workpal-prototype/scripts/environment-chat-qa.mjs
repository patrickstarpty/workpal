import {gotoWorkspace,reloadWorkspace} from './qa-navigation.mjs';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';
const require=createRequire(import.meta.url);
const {chromium,expect}=require(process.env.WORKPAL_PLAYWRIGHT||'@playwright/test');
const browser=await chromium.launch();
const url=pathToFileURL(resolve('dist/Workpal.html')).href;
try{
  for(const width of [1440,390]){
    const page=await browser.newPage({viewport:{width,height:900}}),errors=[];
    page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(8000);
    await gotoWorkspace(page,url+'#chatroom');
    const seeds=await page.evaluate(()=>WorkpalStudio.db.conversations.filter(c=>c.fixtureSource==='environment-chat-v1'));
    expect(seeds).toHaveLength(3);
    for(const c of seeds){
      await page.locator('.thread-scroll [data-id="'+c.id+'"]').click();
      await expect(page.locator('.environment-context')).toContainText(c.environment);
      await expect(page.locator('#assistant .reply')).toHaveCount(c.messages.filter(m=>m.role==='assistant').length);
      await expect(page.getByRole('button',{name:'Send message',exact:true})).toBeInViewport();
      if(width<700)await page.getByRole('button',{name:'Back to conversations',exact:true}).click();
    }
    const uat=seeds.find(c=>c.environment==='UAT');
    await page.locator('.thread-scroll [data-id="'+uat.id+'"]').click();
    const before=await page.evaluate(()=>({notes:JSON.stringify(WorkpalStudio.db.notes),tasks:WorkpalStudio.db.tasks.length,runs:WorkpalStudio.db.runs.length}));
    const prompt=page.getByRole('textbox',{name:'Message',exact:true});
    const log='UAT trace: <img src=x onerror="window.chatInjected=true">\nStill getting a 403 on citation preview.';
    await prompt.fill(log);await prompt.press('Enter');
    await expect(page.locator('#assistant .user-turn').last()).toContainText(log);
    await expect(page.locator('#assistant .user-turn').last()).toContainText('Queued · runtime offline');
    await expect(page.locator('#assistant .reply')).toHaveCount(uat.messages.filter(m=>m.role==='assistant').length);
    expect(await page.evaluate(()=>window.chatInjected)).toBeUndefined();
    const run=await page.evaluate(()=>WorkpalStudio.db.runs[0]);
    expect(run.agent).toBe('Quality partner');expect(run.context.environment).toBe('UAT');expect(run.status).toBe('queued');
    await page.getByRole('button',{name:'Cancel',exact:true}).click();
    await expect(page.locator('#assistant .user-turn').last()).toContainText('Cancelled');
    await prompt.fill('Keep my UAT follow-up draft');
    await page.locator('#assistant .composer [data-id="environmentSetup|UAT"]').click();
    await expect(page.locator('#dialog')).toBeVisible();
    await page.getByLabel('Environment',{exact:true}).selectOption('PRD');
    await expect(page.getByLabel('Agent',{exact:true})).toHaveValue('Engineering partner');
    await page.getByRole('button',{name:'Start conversation',exact:true}).click();
    await expect(page.locator('.environment-context')).toContainText('PRD');
    await prompt.fill('PRD worker stopped accepting uploads.');
    await reloadWorkspace(page);
    await expect(prompt).toHaveValue('PRD worker stopped accepting uploads.');
    await expect(page.locator('.environment-context')).toContainText('PRD');
    await prompt.press('Enter');
    const prd=await page.evaluate(()=>WorkpalStudio.db.conversations.find(c=>c.id===WorkpalStudio.db.currentChat));
    expect(prd.environment).toBe('PRD');expect(prd.messages).toHaveLength(1);
    if(width<700)await page.getByRole('button',{name:'Back to conversations',exact:true}).click();
    await page.locator('.thread-scroll [data-id="'+uat.id+'"]').click();
    await expect(prompt).toHaveValue('Keep my UAT follow-up draft');
    await page.getByRole('button',{name:'Create issue',exact:true}).click();
    const linked=await page.evaluate(id=>{const db=WorkpalStudio.db,c=db.conversations.find(c=>c.id===id);return {task:db.tasks.find(t=>t.id===c.issueId),notes:JSON.stringify(db.notes),runs:db.runs.length};},uat.id);
    expect(linked.task.status).toBe('backlog');expect(linked.task.owner).toBe('Quality partner');expect(linked.task.description).toContain(log);expect(linked.notes).toBe(before.notes);expect(linked.runs).toBe(before.runs+2);
    await gotoWorkspace(page,url+'#chatroom');
    if(width<700&&await page.getByRole('button',{name:'Back to conversations',exact:true}).isVisible())await page.getByRole('button',{name:'Back to conversations',exact:true}).click();
    await page.locator('.thread-scroll [data-id="'+uat.id+'"]').click();
    await expect(page.locator('.environment-context')).toContainText(linked.task.id);
    expect(await page.evaluate(()=>WorkpalStudio.db.tasks.length)).toBe(before.tasks+1);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    expect(errors).toEqual([]);
    await page.close();
    console.log('PASS environment chat '+width+'px: histories, routing, text safety, offline queue/cancel, drafts, reload, issue handoff, notes, layout.');
  }
}finally{await browser.close();}
