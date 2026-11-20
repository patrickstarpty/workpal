import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';
const require=createRequire(import.meta.url),{chromium,expect}=require(process.env.WORKPAL_PLAYWRIGHT||'@playwright/test');
const browser=await chromium.launch();
try{
 for(const width of [1440,390]){
  const page=await browser.newPage({viewport:{width,height:900}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(resolve('dist/Workpal.html')).href);await page.evaluate(()=>document.fonts.ready);
  await expect(page.locator('.welcome-brand .brand-logo')).toBeVisible();await expect(page.locator('.welcome-brand .brand-wordmark')).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  await page.screenshot({path:`test-results/brand-welcome-${width}.png`});
  await page.locator('.welcome-enter').click();
  await expect(page.locator('.chat-launcher .brand-logo')).toBeVisible();
  if(width===1440)await expect(page.locator('.product-wordmark .brand-wordmark')).toBeVisible();
  expect(await page.locator('link[rel=icon]').getAttribute('href')).toMatch(/^data:image\/svg\+xml;base64,/);
  await page.evaluate(()=>location.hash='#stats?tab=contribution');
  await expect(page.locator('.viz-total')).toBeVisible();expect(await page.locator('.viz-total').evaluate(e=>getComputedStyle(e).fontSize)).toBe('28px');
  expect(errors).toEqual([]);await page.close();
 }
 console.log('Brand QA passed: welcome, footer, assistant, embedded favicon and chart typography; desktop/mobile.');
}finally{await browser.close();}
