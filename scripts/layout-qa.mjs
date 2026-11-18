import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';
import {mkdir} from 'node:fs/promises';

const require=createRequire(import.meta.url);
const {chromium,expect}=require(process.env.WORKPAL_PLAYWRIGHT||'@playwright/test');
const path=pathToFileURL(resolve('dist/Workpal.html')).href;
const viewports=[
  {width:1440,height:900},
  {width:1280,height:720},
  {width:390,height:844},
  {width:390,height:600},
  {width:960,height:480},
];
const browser=await chromium.launch();
const failures=[];
await mkdir('test-results',{recursive:true});

async function geometry(locator){
  return locator.evaluate(element=>{
    const r=element.getBoundingClientRect();
    return {top:r.top,bottom:r.bottom,left:r.left,right:r.right,width:r.width,height:r.height,
      clientHeight:element.clientHeight,scrollHeight:element.scrollHeight,
      clientWidth:element.clientWidth,scrollWidth:element.scrollWidth,
      scrollTop:element.scrollTop,scrollLeft:element.scrollLeft};
  });
}
function close(actual,expected,label,tolerance=2){
  expect(Math.abs(actual-expected),label+': '+actual+' vs '+expected).toBeLessThanOrEqual(tolerance);
}
async function layout(page,name){
  await page.locator('.top').getByRole('button',{name:'Display',exact:true}).click();
  await page.getByRole('button',{name:name+' view',exact:true}).click();
  await expect(page.locator(name==='Board'?'.board':'.issue-groups')).toBeVisible();
}
async function boundedBoard(page,label){
  const main=await geometry(page.locator('main'));
  const board=await geometry(page.locator('.board'));
  close(board.bottom,main.bottom,label+' board reaches viewport bottom');
  expect(main.scrollHeight,label+' main has no board vertical overflow').toBeLessThanOrEqual(main.clientHeight+1);
  expect(board.scrollWidth,label+' board owns horizontal overflow').toBeGreaterThan(board.clientWidth);
  expect(board.scrollHeight,label+' board does not grow with cards').toBeLessThanOrEqual(board.clientHeight+1);
  const lanes=await page.locator('.board-lane').all();
  const widths=[];
  for(const lane of lanes){
    const laneBounds=await geometry(lane);
    widths.push(laneBounds.width);
    close(laneBounds.width,280,label+' reference column width',1);
    const card=lane.locator('.issue-card').first();
    if(await card.count()){
      const cardBounds=await geometry(card);
      close(cardBounds.width,256,label+' reference card width',1);
    }
  }
  close(Math.max(...widths),Math.min(...widths),label+' consistent column widths',1);
  await page.locator('.board').evaluate(element=>element.scrollLeft=300);
  expect((await geometry(page.locator('.board'))).scrollLeft,label+' horizontal scrolling works').toBeGreaterThan(0);
  await page.locator('.board').evaluate(element=>element.scrollLeft=0);
  return board;
}
async function filters(page,label){
  const before=await boundedBoard(page,label);
  await page.getByRole('button',{name:'Filter issues',exact:true}).click();
  await expect(page.locator('.issue-filters')).toBeVisible();
  const after=await boundedBoard(page,label+' with filters');
  expect(after.top,label+' filters reserve vertical space').toBeGreaterThan(before.top);
  await page.getByRole('button',{name:'Filter issues',exact:true}).click();
  const restored=await boundedBoard(page,label+' after filters');
  close(restored.top,before.top,label+' filter height is restored');
}

try {
  for(const viewport of viewports){
    // Every viewport gets a new ephemeral context. Seed mutations cannot reach user storage.
    const context=await browser.newContext({viewport});
    const page=await context.newPage();
    page.setDefaultTimeout(7000);
    const errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    const label=viewport.width+'x'+viewport.height;
    try {
      await page.goto(path+'#tasks');
      await layout(page,'Board');
      await filters(page,label+' sparse');
      if(viewport.width===1440||viewport.height===844)
        await page.screenshot({path:'test-results/layout-board-sparse-'+label+'.png'});

      await page.evaluate(()=>{
        const db=WorkpalStudio.db,seed=db.tasks[0];
        for(let i=0;i<90;i++)db.tasks.push({...structuredClone(seed),id:'LAYOUT-'+(100+i),
          title:'Layout check '+i+' — verify long issue titles remain inside their container',
          status:i<60?'backlog':['todo','active','review','blocked','done'][i%5],activity:[]});
        for(let i=0;i<40;i++)db.agents.push({...structuredClone(db.agents[0]),name:'Layout agent '+i});
        db.conversations=Array.from({length:30},(_,i)=>({id:'layout-chat-'+i,agent:db.agents[0].name,
          title:'Layout conversation '+i,project:'TAP',draft:'',messages:Array.from({length:20},(_,j)=>({
            role:'user',text:'Message '+j+' checks independent transcript scrolling.',at:Date.now()}))}));
        db.currentChat=null;
        WorkpalStudio.save();
      });
      await page.reload();
      await layout(page,'Board');
      await filters(page,label+' long');
      const lane=page.locator('.board-lane').first();
      const headerBefore=await geometry(lane.locator('.issue-group-header'));
      const cardsBefore=await geometry(lane.locator('.board-cards'));
      expect(cardsBefore.scrollHeight,label+' long column scrolls').toBeGreaterThan(cardsBefore.clientHeight+200);
      await lane.locator('.board-cards').evaluate(element=>element.scrollTop=500);
      expect((await geometry(lane.locator('.board-cards'))).scrollTop,label+' card scroll moves').toBeGreaterThan(0);
      close((await geometry(lane.locator('.issue-group-header'))).top,headerBefore.top,label+' lane header stays fixed');
      close((await geometry(page.locator('main'))).scrollTop,0,label+' lane scroll does not scroll page');
      if(viewport.width===1440||viewport.height===844)
        await page.screenshot({path:'test-results/layout-board-long-'+label+'.png'});

      await page.locator('.board').evaluate(element=>element.scrollLeft=300);
      const scrollBefore=await geometry(page.locator('.board'));
      await page.goto(path+'#agents');
      await expect(page.locator('.agent-table')).toBeVisible();
      await page.goto(path+'#tasks');
      close((await geometry(page.locator('.board'))).scrollLeft,scrollBefore.scrollLeft,label+' board restores horizontal position');
      close((await geometry(page.locator('.board-cards').first())).scrollTop,500,label+' column restores vertical position');

      await page.goto(path+'#tasks?id=TAP-030');
      await expect(page.locator('.detail-reading h1')).toBeVisible();
      if(viewport.width>=768){
        const properties=await geometry(page.locator('.detail-properties'));
        close(properties.top,(await geometry(page.locator('.main'))).top,label+' properties align to full page top');
        await expect(page.getByRole('button',{name:'Post comment',exact:true})).toBeInViewport();
      }
      expect(await page.locator('main').evaluate(el=>el.scrollWidth-el.clientWidth),label+' detail fits viewport').toBeLessThanOrEqual(1);
      if(viewport.width===1440||viewport.height===844)
        await page.screenshot({path:'test-results/layout-detail-'+label+'.png'});
      await page.goto(path+'#tasks');

      await layout(page,'List');
      const groups=page.locator('.issue-groups');
      const listBefore=await geometry(groups);
      expect(listBefore.scrollHeight,label+' list has its own scroll area').toBeGreaterThan(listBefore.clientHeight+200);
      const gap=await page.locator('.issue-group').evaluateAll(elements=>
        elements[1].getBoundingClientRect().top-elements[0].getBoundingClientRect().bottom);
      expect(gap,label+' list groups do not overlap').toBeGreaterThanOrEqual(0);
      expect(gap,label+' list group spacing stays compact').toBeLessThanOrEqual(32);
      const topBefore=await geometry(page.locator('.top'));
      const sidebarBefore=await geometry(page.locator('.space-panel'));
      await groups.evaluate(element=>element.scrollTop=400);
      const groupHeader=await geometry(page.locator('.issue-group-header').first());
      close(groupHeader.top,listBefore.top,label+' list group heading stays visible',10);
      close((await geometry(page.locator('.top'))).top,topBefore.top,label+' page heading stays fixed');
      close((await geometry(page.locator('.space-panel'))).top,sidebarBefore.top,label+' sidebar stays fixed');
      close((await geometry(page.locator('main'))).scrollTop,0,label+' list scroll stays contained');

      await page.goto(path+'#agents');
      const table=page.locator('.agent-table');
      const tableBefore=await geometry(table);
      expect(tableBefore.scrollHeight,label+' agent table owns scrolling').toBeGreaterThan(tableBefore.clientHeight);
      const tableHeadBefore=await geometry(page.locator('.table-head'));
      await table.evaluate(element=>element.scrollTop=400);
      close((await geometry(page.locator('.table-head'))).top,tableHeadBefore.top,label+' table header stays fixed');
      close((await geometry(page.locator('main'))).scrollTop,0,label+' table scroll stays contained');

      await page.goto(path+'#overview');
      const overview=await geometry(page.locator('main'));
      expect(overview.scrollWidth,label+' long review titles fit overview').toBeLessThanOrEqual(overview.clientWidth+1);

      await page.goto(path+'#chatroom');
      const thread=page.locator('.thread-scroll');
      const threadBefore=await geometry(thread);
      expect(threadBefore.scrollHeight,label+' conversation list owns scrolling').toBeGreaterThan(threadBefore.clientHeight);
      const threadHeader=await geometry(page.locator('.thread-list>header'));
      await thread.evaluate(element=>element.scrollTop=400);
      close((await geometry(page.locator('.thread-list>header'))).top,threadHeader.top,label+' Chat list heading stays fixed');
      await page.locator('.thread-scroll [data-id="layout-chat-0"]').click();
      const composerBefore=await geometry(page.locator('.composer'));
      await page.locator('.messages').evaluate(element=>element.scrollTop=element.scrollHeight);
      close((await geometry(page.locator('.composer'))).bottom,composerBefore.bottom,label+' composer stays fixed');
      expect(composerBefore.bottom,label+' composer is inside main').toBeLessThanOrEqual((await geometry(page.locator('main'))).bottom+1);
      expect(composerBefore.right,label+' composer fits mobile width').toBeLessThanOrEqual(viewport.width);
      if(viewport.width<768){
        await expect(page.locator('.thread-list')).not.toBeVisible();
        await page.getByRole('button',{name:'Back to conversations',exact:true}).click();
        await expect(page.locator('.thread-list')).toBeVisible();
        await expect(page.locator('#chat-pane')).not.toBeVisible();
      }
      expect(await page.evaluate(()=>document.documentElement.scrollWidth),label+' no viewport horizontal overflow').toBeLessThanOrEqual(viewport.width);
      expect(errors,label+' no browser errors').toEqual([]);
      console.log('PASS layout '+label);
    } catch(error) {
      failures.push(label+': '+error.message);
      await page.screenshot({path:'test-results/layout-failure-'+label+'.png'});
    } finally {
      await context.close();
    }
  }
} finally {
  await browser.close();
}
if(failures.length)throw new Error(failures.join('\n\n'));
console.log('Layout QA passed for all '+viewports.length+' viewport sizes.');
