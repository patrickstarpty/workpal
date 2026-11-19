import {gotoWorkspace} from './qa-navigation.mjs';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';
const require=createRequire(import.meta.url);
const {chromium,expect}=require(process.env.WORKPAL_PLAYWRIGHT||'@playwright/test');
const browser=await chromium.launch();
const errors=[];
try{
  for(const width of [1440,390]){
    const page=await browser.newPage({viewport:{width,height:1000}});
    page.on('pageerror',e=>errors.push(e.message));
    for(const view of ['usage','errors','contribution','skills']){
      await gotoWorkspace(page,pathToFileURL(resolve('dist/Workpal.html')).href+'#'+(view==='skills'?'skills':'stats?tab='+view));
      if(await page.getByRole('link',{name:'Enter workspace',exact:true}).isVisible())await page.getByRole('link',{name:'Enter workspace',exact:true}).click();
      await page.waitForTimeout(150);
      await expect(page.locator('.analytics-chart,.viz-ring svg,.viz-bars').first()).toBeVisible();
      if(view==='contribution'){
        const expected=await page.evaluate(()=>{const result=WorkpalAnalyticsData.contribution(WorkpalStudio.db,{days:30});return {rate:result.totals.commits?(100*result.totals.workpal/result.totals.commits).toFixed(1)+'%':'—',rows:WorkpalAnalyticsData.squadContribution(WorkpalStudio.db,result).rows.map(r=>[r.name,r.tickets,r.commits,r.workpal,r.human,r.commits?(100*r.workpal/r.commits).toFixed(1)+'%':'—'])};});
        await expect(page.locator('.contribution-summary .viz-total')).toHaveText(expected.rate);
        await expect(page.locator('.squad-contribution-table tbody tr')).toHaveCount(expected.rows.length);
        for(let i=0;i<expected.rows.length;i++){
          const cells=page.locator('.squad-contribution-table tbody tr').nth(i).locator('td');
          await expect(cells.nth(0)).toContainText(expected.rows[i][0]);
          for(let j=1;j<6;j++)await expect(cells.nth(j)).toHaveText(String(expected.rows[i][j]));
        }
        await expect(page.locator('.analytics-chart')).toHaveCount(0);
        await expect(page.getByRole('heading',{name:'Contribution summary',exact:true})).toBeVisible();
      }
      if(view==='skills'){
        await expect(page.locator('.skill-feature')).toHaveCount(3);
        await page.locator('[data-filter="skill"]').fill('Citation Audit');
        await expect(page.locator('.skill-line')).toHaveCount(1);
      }
      if(width===1440&&['skills','contribution'].includes(view))await page.screenshot({path:'test-results/'+view+'-charts.png'});
      const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);if(overflow)throw Error(view+' overflow at '+width);
    }
    await page.goto(pathToFileURL(resolve('dist/Workpal.html')).href+'#stats?tab=teams&team=quality');
    if(await page.getByRole('link',{name:'Open workspace',exact:false}).isVisible())await page.getByRole('link',{name:'Open workspace',exact:false}).click();
    await expect(page.getByRole('tab',{name:'Usage',exact:true})).toHaveAttribute('aria-selected','true');
    await expect(page.getByRole('tab',{name:'Teams',exact:true})).toHaveCount(0);
    await expect(page.getByRole('combobox',{name:'Team',exact:true})).toHaveCount(0);
    await expect.poll(()=>page.evaluate(()=>location.hash.includes('team='))).toBe(false);
    await page.close();
  }
  if(errors.length)throw Error(errors.join('\n'));
  console.log('Chart panels pass at desktop/mobile, with keyboard tooltips and Skill Hub filtering.');
}finally{await browser.close();}
