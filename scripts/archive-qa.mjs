import {createRequire} from 'node:module';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {gotoWorkspace,reloadWorkspace} from './qa-navigation.mjs';
const require=createRequire(import.meta.url);
let playwright;
for(const candidate of [process.env.WORKPAL_PLAYWRIGHT,'@playwright/test','/tmp/tap-browser-mj_qfqun/node_modules/@playwright/test','../multica/node_modules/@playwright/test'].filter(Boolean)){
  try{playwright=require(candidate);break;}catch(error){if(error.code!=='MODULE_NOT_FOUND')throw error;}
}
if(!playwright)throw Error('Playwright unavailable; set WORKPAL_PLAYWRIGHT.');
const {chromium,expect}=playwright,browser=await chromium.launch();
const url=pathToFileURL(resolve('dist/Workpal.html')).href;
try{
  for(const width of [1440,390]){
    const context=await browser.newContext({viewport:{width,height:width===390?844:1000}}),page=await context.newPage(),errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await gotoWorkspace(page,url+'#tasks');
    const workspaceId=await page.evaluate(()=>WorkpalStudio.createWorkspace('Archive QA'));
    await gotoWorkspace(page,url+'#w/'+workspaceId+'/tasks');
    await page.evaluate(()=>{
      const db=WorkpalStudio.db;
      db.projects=['Archive QA'];
      db.tasks=Array.from({length:10000},(_,i)=>({id:'ARC-'+String(i+1).padStart(5,'0'),title:'Completed '+(i+1),status:'done',owner:i%2?'Patrick':'Unassigned',project:'Archive QA',team:'engineering',priority:'Normal',description:'Keep delivery history',checks:[],activity:[],tags:[],stage:5}));
      db.tasks.push({id:'ARC-OPEN',title:'Open work',status:'todo',owner:'Patrick',project:'Archive QA',team:'engineering',priority:'Normal',description:'',checks:[],activity:[],tags:[],stage:1});
      db.issueDisplay={layout:'list',hidden:[],collapsed:[],properties:['priority','project','assignee','due','children']};
      db.notes=[{id:'preserve-note',text:'Review note stays here'}];
      WorkpalStudio.save();
    });
    await reloadWorkspace(page);
    const done=()=>page.locator('[data-group="done"]');
    await expect(done().locator('.issue.row')).toHaveCount(50);
    await expect(done().locator('.issue-pagination')).toContainText('1–50 of 10,000');
    await page.getByRole('button',{name:'Next Done page',exact:true}).focus();
    await page.keyboard.press('Enter');
    await expect(done().locator('.issue-pagination')).toContainText('51–100 of 10,000');
    await page.getByRole('button',{name:'Archive this page',exact:true}).click();
    await expect(page.getByRole('region',{name:'Review archive selection'})).toContainText('Archive 50 completed issues?');
    await page.getByRole('button',{name:'Archive 50 issues',exact:true}).click();
    expect(await page.evaluate(()=>WorkpalStudio.db.tasks.filter(t=>t.archivedAt).length)).toBe(50);
    await expect(done().locator('.issue.row')).toHaveCount(50);
    await expect(done().locator('.issue-group-header')).toContainText('9,950');
    await page.getByRole('link',{name:'Archived 50',exact:true}).click();
    await expect(page.locator('.archived-issue')).toHaveCount(50);
    const firstId=await page.locator('.archived-issue .issue-id').first().textContent();
    await page.locator('.archived-issue .issue').first().click();
    await expect(page.locator('.issue-archived-banner')).toContainText('Archived · Done');
    await expect(page.getByRole('button',{name:'Edit issue',exact:true})).toHaveCount(0);
    await expect(page.getByRole('textbox',{name:'Add a comment',exact:true})).toHaveCount(0);
    await expect(page.locator('[data-id="issueProperty|'+firstId+'|status"]')).toHaveCount(0);
    await page.getByRole('button',{name:'Restore issue',exact:true}).click();
    expect(await page.evaluate(id=>{const t=WorkpalStudio.db.tasks.find(t=>t.id===id);return [t.status,!!t.archivedAt];},firstId)).toEqual(['done',false]);
    await gotoWorkspace(page,url+'#w/'+workspaceId+'/tasks?archive=1');
    await page.getByRole('button',{name:'Restore this page',exact:true}).click();
    await expect(page.locator('.archived-issue')).toHaveCount(0);
    await page.getByRole('link',{name:'All issues',exact:true}).last().click();
    await page.getByRole('button',{name:'Display',exact:true}).click();
    await page.getByRole('button',{name:'Board view',exact:true}).click();
    await expect(page.locator('[data-drop-state="done"] .issue-card')).toHaveCount(50);
    await page.getByRole('button',{name:'Archive all 10,000 matching',exact:true}).click();
    await page.getByRole('button',{name:'Archive 10,000 issues',exact:true}).click();
    expect(await page.evaluate(()=>WorkpalStudio.db.tasks.filter(t=>t.archivedAt).length)).toBe(10000);
    await expect(page.locator('[data-drop-state="done"] .issue-card')).toHaveCount(0);
    await expect(page.locator('[data-drop-state="todo"] .issue-card')).toHaveCount(1);
    await reloadWorkspace(page);
    expect(await page.evaluate(()=>[WorkpalStudio.db.tasks.filter(t=>t.archivedAt).length,WorkpalStudio.db.notes[0].text])).toEqual([10000,'Review note stays here']);
    await page.getByRole('link',{name:'Archived 10,000',exact:true}).click();
    await expect(page.locator('.archived-issue')).toHaveCount(50);
    await page.getByRole('button',{name:'Next archived page',exact:true}).click();
    await expect(page.locator('.issue-archive-toolbar')).toContainText('51–100 of 10,000');
    await page.getByRole('textbox',{name:'Filter issues',exact:true}).fill('ARC-09999');
    await expect(page.locator('.archived-issue')).toHaveCount(1);
    await page.getByRole('button',{name:'Restore ARC-09999',exact:true}).click();
    await expect(page.locator('.archived-issue')).toHaveCount(0);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
    expect(errors).toEqual([]);
    console.log(`${width}px: 10,000 Done rows bounded to 50, page/all archive, archive pagination/search, detail/page restore, persistence and notes passed`);
    await context.close();
  }
}finally{await browser.close();}
