import {gotoWorkspace,reloadWorkspace} from './qa-navigation.mjs';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';
import {mkdir} from 'node:fs/promises';

const require=createRequire(import.meta.url);
const {chromium,expect}=require(process.env.WORKPAL_PLAYWRIGHT||'@playwright/test');
const artifact=pathToFileURL(resolve('dist/Workpal.html')).href;
const viewports=[{width:1440,height:900},{width:1280,height:800},{width:728,height:900},{width:390,height:844}];
const browser=await chromium.launch();
const failures=[];
await mkdir('test-results',{recursive:true});

async function tab(page,name){
  await page.getByRole('tab',{name,exact:true}).click();
  await expect(page.getByRole('tab',{name,exact:true})).toHaveAttribute('aria-selected','true');
  await expect(page.getByRole('tabpanel')).toHaveAttribute('aria-labelledby','analytics-tab-'+name.toLowerCase());
}
async function choose(page,label,value){
  await page.getByRole('combobox',{name:label,exact:true}).selectOption(value);
  await expect(page.getByRole('combobox',{name:label,exact:true})).toHaveValue(value);
}
async function pressed(page,group,name){
  return expect(page.getByRole('group',{name:group,exact:true}).getByRole('button',{name,exact:true})).toHaveAttribute('aria-pressed','true');
}
async function pick(page,group,name){
  await page.getByRole('group',{name:group,exact:true}).getByRole('button',{name,exact:true}).click();
  await pressed(page,group,name);
}
async function headline(page){
  const expected=await page.evaluate(()=>{
    const params=new URLSearchParams(location.hash.split('?')[1]||'');
    const days=Number(params.get('days')||30),team=params.get('team')||'',project=params.get('project')||'';
    const active=params.get('tab')||(team?'teams':'usage'),db=WorkpalStudio.db;
    const d=WorkpalAnalyticsData,t=d.snapshot(db,{days,team,project}).totals;
    if(active==='teams'){
      const issues=db.tasks.filter(issue=>(!team||issue.team===team)&&(!project||issue.project===project));
      return [issues.length,...['active','review','done'].map(status=>issues.filter(issue=>issue.status===status).length)].map(String);
    }
    if(active==='errors')return [String(t.failed),d.rate(t.failed,t.runs),String(t.affected)];
    return t.runs?[d.money(t.cost),d.compact(t.tokens),d.duration(t.seconds),String(t.runs)]:[];
  });
  await expect(page.locator('.analytics-value')).toHaveText(expected);
}
async function bounded(page,viewport){
  expect(await page.evaluate(()=>document.documentElement.scrollWidth),'no document horizontal overflow').toBeLessThanOrEqual(viewport.width+1);
  for(const region of await page.locator('.analytics-table-scroll').all()){
    const size=await region.evaluate(el=>({width:el.clientWidth,scroll:el.scrollWidth,right:el.getBoundingClientRect().right}));
    expect(size.right,'table viewport stays inside screen').toBeLessThanOrEqual(viewport.width+1);
    if(viewport.width<600)expect(size.scroll,'wide data table scrolls inside its region').toBeGreaterThan(size.width);
  }
  const before=await page.locator('.top').boundingBox();
  await page.locator('main').evaluate(el=>el.scrollTop=el.scrollHeight);
  const after=await page.locator('.top').boundingBox();
  expect(Math.abs(before.y-after.y),'analytics header stays fixed while main scrolls').toBeLessThanOrEqual(1);
  await page.locator('main').evaluate(el=>el.scrollTop=0);
}
async function screenshot(page,tabName,viewport){
  await bounded(page,viewport);
  if(viewport.width===1440||viewport.width===390)
    await page.screenshot({path:'test-results/analytics-'+tabName+'-'+viewport.width+'x'+viewport.height+'.png'});
}
async function switchWorkspace(page,current,next){
  const switcher=page.getByRole('button',{name:'Switch workspace, '+current,exact:true});
  if(!await switcher.isVisible())await page.getByRole('button',{name:'Workspace menu',exact:true}).click();
  await switcher.click();
  await page.locator('#dialog [data-act=switchSpace]').filter({hasText:next}).click();
  await expect.poll(()=>page.evaluate(()=>WorkpalStudio.workspace.name)).toBe(next);
  const id=await page.evaluate(()=>WorkpalStudio.workspace.id);
  await gotoWorkspace(page,artifact+'#'+(id==='tap'?'':'w/'+id+'/')+'stats');
  await expect(page.getByRole('heading',{name:'Analytics',exact:true})).toBeVisible();
}

try{
  for(const viewport of viewports){
    const context=await browser.newContext({viewport});
    const page=await context.newPage();
    page.setDefaultTimeout(7000);
    const label=viewport.width+'x'+viewport.height,errors=[];
    page.on('pageerror',error=>errors.push(error.message));
    try{
      await gotoWorkspace(page,artifact+'#stats');
      await expect(page.getByRole('heading',{name:'Analytics',exact:true})).toBeVisible();
      await headline(page);
      await screenshot(page,'usage',viewport);

      await pick(page,'Trend metric','Cost');
      await pick(page,'Rank agents by','Time');
      await pressed(page,'Trend metric','Cost');
      await expect(page.getByRole('heading',{name:'Daily cost',exact:true})).toBeVisible();
      await pick(page,'Chart interval','Weekly');
      await expect(page.getByRole('combobox',{name:'Period',exact:true})).toHaveValue('30');
      await pressed(page,'Rank agents by','Time');
      for(const days of ['1','7','30','90','180']){
        await choose(page,'Period',days);
        await headline(page);
        if(days==='30'||days==='90'){
          await pressed(page,'Chart interval','Weekly');
          await expect(page.getByRole('heading',{name:'Weekly cost',exact:true})).toBeVisible();
        }else{
          await expect(page.getByRole('group',{name:'Chart interval',exact:true})).toHaveCount(0);
          if(await page.locator('.analytics-value').count())await expect(page.getByRole('heading',{name:(days==='180'?'Weekly':'Daily')+' cost',exact:true})).toBeVisible();
        }
        if(await page.locator('.analytics-value').count())await pressed(page,'Rank agents by','Time');
      }
      await choose(page,'Period','30');
      await pick(page,'Chart interval','Daily');
      await pick(page,'Trend metric','Tokens');
      const point=page.locator('[data-analytics-point]').first();
      await point.hover();
      await expect(page.getByRole('tooltip')).toBeVisible();
      await expect(page.getByRole('tooltip')).toContainText('Total:');
      await page.keyboard.press('Escape');
      await expect(page.getByRole('tooltip')).not.toBeVisible();
      await point.focus();
      await expect(page.getByRole('tooltip')).toBeVisible();
      await page.getByRole('combobox',{name:'Period',exact:true}).focus();
      await expect(page.getByRole('tooltip')).not.toBeVisible();

      await choose(page,'Project','TAP');
      await choose(page,'Team','quality');
      await headline(page);
      await expect(page.getByRole('region',{name:'Agent leaderboard',exact:true}).locator('tbody tr')).toHaveCount(1);
      await expect(page.getByRole('region',{name:'Agent leaderboard',exact:true})).toContainText('Quality partner');
      await tab(page,'Errors');
      await headline(page);
      await choose(page,'Project','');
      await choose(page,'Team','');
      await headline(page);
      await screenshot(page,'errors',viewport);
      await page.getByRole('button',{name:'Show error codes',exact:true}).click();
      await expect(page.locator('.analytics-mix code').first()).toBeVisible();
      await page.getByRole('button',{name:'Hide error codes',exact:true}).click();
      await expect(page.locator('.analytics-mix code')).toHaveCount(0);
      await pick(page,'Rank offenders by','Rate');
      const expectedOrder=await page.evaluate(()=>{
        const s=WorkpalAnalyticsData.snapshot(WorkpalStudio.db,{days:30});
        return s.agents.filter(a=>a.failed).sort((a,b)=>Number(b.runs>=10)-Number(a.runs>=10)||b.failureRate-a.failureRate).slice(0,8).map(a=>a.name);
      });
      await expect(page.getByRole('region',{name:'Top offenders',exact:true}).locator('.analytics-agent>span:last-child')).toHaveText(expectedOrder);
      await pick(page,'Chart interval','Weekly');
      await tab(page,'Usage');
      await pressed(page,'Chart interval','Daily');
      await pressed(page,'Rank agents by','Time');
      await tab(page,'Errors');
      await pressed(page,'Chart interval','Weekly');

      await tab(page,'Teams');
      await headline(page);
      await screenshot(page,'teams',viewport);
      await page.getByRole('region',{name:'Workload by team',exact:true}).getByRole('button',{name:'Quality',exact:true}).click();
      await expect(page.getByRole('combobox',{name:'Team',exact:true})).toHaveValue('quality');
      await expect(page.getByRole('heading',{name:'Quality issues',exact:true})).toBeVisible();
      await headline(page);
      await page.getByRole('button',{name:/View usage/}).click();
      await expect(page.getByRole('tab',{name:'Usage',exact:true})).toHaveAttribute('aria-selected','true');
      await expect(page.getByRole('combobox',{name:'Team',exact:true})).toHaveValue('quality');
      await headline(page);
      await tab(page,'Teams');
      const issue=page.locator('.analytics-team-issues [data-id^="issue|"]').first();
      const issueId=(await issue.getAttribute('data-id')).split('|')[1];
      await issue.click();
      await expect(page.locator('.shell')).toHaveAttribute('data-detail','true');
      expect(new URLSearchParams((await page.evaluate(()=>location.hash)).split('?')[1]).get('id')).toBe(issueId);
      await gotoWorkspace(page,artifact+'#stats');
      await switchWorkspace(page,'TAP','Symphony');
      await expect(page.getByRole('heading',{name:'No usage yet',exact:true})).toBeVisible();
      await expect(page.locator('.analytics-value')).toHaveCount(0);
      await tab(page,'Errors');
      await headline(page);
      await expect(page.getByRole('heading',{name:'No failed runs in this window',exact:true})).toBeVisible();
      await tab(page,'Teams');
      await headline(page);
      await expect(page.locator('.analytics-value')).toHaveText(['0','0','0','0']);
      await switchWorkspace(page,'Symphony','TAP');
      await headline(page);
      await expect(page.getByRole('heading',{name:'Leaderboard',exact:true})).toBeVisible();
      await bounded(page,viewport);
      expect(errors,'no browser errors').toEqual([]);
      console.log('PASS analytics '+label);
    }catch(error){
      failures.push(label+': '+error.message);
      await page.screenshot({path:'test-results/analytics-failure-'+label+'.png'});
    }finally{await context.close();}
  }
}finally{await browser.close();}
if(failures.length)throw Error(failures.join('\n\n'));
console.log('Analytics QA passed for all '+viewports.length+' viewport sizes.');
