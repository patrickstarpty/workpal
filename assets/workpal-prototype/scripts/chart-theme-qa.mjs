import {gotoWorkspace} from './qa-navigation.mjs';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';
const require=createRequire(import.meta.url);
const {chromium,expect}=require(process.env.WORKPAL_PLAYWRIGHT||'@playwright/test');
const browser=await chromium.launch();
const url=pathToFileURL(resolve('dist/Workpal.html')).href;
try{
 const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 for(const theme of ['neutral','warm','neutral']){
  await gotoWorkspace(page,url+'#settings');
  await page.locator('#workspace-theme').selectOption(theme);
  await expect(page.locator('html')).toHaveAttribute('data-theme',theme);
  for(const route of ['stats?tab=usage','stats?tab=errors','stats?tab=contribution','skills']){
   await gotoWorkspace(page,url+'#'+route);
   await expect(page.locator('html')).toHaveAttribute('data-theme',theme);
   if(route==='stats?tab=errors'){
    await page.evaluate(()=>{delete WorkpalStudio.db.analyticsHistory;WorkpalAnalyticsData.ensure(WorkpalStudio.db,'tap');WorkpalStudio.save();});
    await page.getByRole('button',{name:'Refresh analytics',exact:true}).click();
    const failure=page.locator('rect[fill="var(--analytics-error-1)"]').first();await expect(failure).toBeVisible();
    if(theme==='warm')expect(await failure.evaluate(e=>getComputedStyle(e).fill)).toBe('rgb(169, 71, 40)');
   }
   const expected=theme==='warm'?'rgb(232, 119, 34)':'rgb(87, 124, 170)';
   const ring=page.locator('.viz-ring circle[stroke="var(--chart-series-1)"]');
   if(await ring.count())expect(await ring.first().evaluate(e=>getComputedStyle(e).stroke)).toBe(expected);
   const line=page.locator('polyline[stroke="var(--chart-series-1)"]');
   if(await line.count())expect(await line.first().evaluate(e=>getComputedStyle(e).stroke)).toBe(expected);
   for(const selector of ['.viz-track b','.contribution-stacked i:first-child']){
    const bars=page.locator(selector);if(await bars.count())expect(await bars.first().evaluate(e=>getComputedStyle(e).backgroundColor)).toBe(expected);
   }
   if(route==='stats?tab=usage'){
    const mark=page.locator('rect[fill="var(--analytics-blue-1)"]').first();
    await expect(mark).toBeVisible();const fill=await mark.evaluate(e=>getComputedStyle(e).fill);
    expect(fill).toBe(theme==='warm'?'rgb(232, 119, 34)':'oklch(0.55 0.16 255)');
   }
  }
 }
 expect(errors).toEqual([]);
 console.log('Chart theme QA passed: Neutral → Warm → Neutral via Settings, persisted across Analytics and Skill Hub.');
}finally{await browser.close();}
