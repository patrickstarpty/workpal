import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';
import {gotoWorkspace} from './qa-navigation.mjs';
const require=createRequire(import.meta.url);
let pw;
for(const path of [process.env.WORKPAL_PLAYWRIGHT,'@playwright/test','/tmp/tap-browser-mj_qfqun/node_modules/@playwright/test','../multica/node_modules/@playwright/test'].filter(Boolean)){try{pw=require(path);break;}catch{}}
if(!pw)throw Error('Set WORKPAL_PLAYWRIGHT to a local Playwright package.');
const {chromium,expect}=pw,browser=await chromium.launch();
try{for(const width of [1440,390]){
 const context=await browser.newContext({viewport:{width,height:900}}),page=await context.newPage(),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await gotoWorkspace(page,pathToFileURL(resolve('dist/Workpal.html')).href+'#tasks');
 await page.keyboard.press('Control+k');
 await expect(page.locator('.command-result')).toHaveCount(2);
 const query=page.locator('#command-input');await query.fill('Engineering');await query.press('ArrowDown');await expect(query).toBeFocused();await query.press('x');await expect(query).toHaveValue('Engineeringx');await expect(page.locator('.command-result')).toHaveCount(0);await query.press('ArrowDown');await query.press('Escape');
 await page.keyboard.press('c');await expect(page.locator('#dialog [name=title]')).toBeFocused();
 await page.locator('#dialog [name=title]').fill('<title> draft');
 const picker=page.locator('#dialog [data-picker-select]').first();await picker.click();await expect(page.locator('.property-picker')).toBeVisible();
 const bounds=await page.locator('.property-picker').boundingBox();if(bounds.x<0||bounds.x+bounds.width>width)throw Error('Picker overflow');
 await page.locator('.property-picker input').press('Escape');await expect(picker).toBeFocused();
 await page.keyboard.press('Escape');await page.keyboard.press('c');await expect(page.locator('#dialog [name=title]')).toHaveValue('<title> draft');
 await expect(page.locator('#dialog title')).toHaveCount(0);
 await page.keyboard.press('Escape');
 await page.evaluate(()=>location.hash='#projects');await expect(page.locator('.collection')).toBeVisible();
 await page.keyboard.press('/');await expect(page.locator('[data-collection-search]')).toBeFocused();await page.locator('[data-collection-search]').fill('Skill');await expect(page.locator('.collection-row:not(.collection-head)')).toHaveCount(1);
 await page.locator('[data-collection-check]').check();await expect(page.locator('.collection-selection')).toContainText('1 selected');
 await page.evaluate(()=>location.hash='#tasks');
 await page.getByRole('button',{name:'Display',exact:true}).click();await page.getByRole('button',{name:'Board view',exact:true}).click();
 const card=page.locator('.issue-card').first();await card.focus();await card.press('Space');await expect(page.locator('#dialog[data-surface=peek]')).toBeVisible();
 const title=page.locator('#dialog [data-inline-field=title]');await title.fill('Inline edited title');await title.press('Tab');await page.keyboard.press('Escape');await expect(page.locator('.issue-card').first()).toContainText('Inline edited title');
 await page.locator('.issue-card').first().getByRole('button',{name:'Change priority'}).click();await expect(page.locator('.property-picker')).toBeVisible();await page.locator('.property-picker').getByRole('option',{name:'Urgent',exact:true}).click();
 if(errors.length)throw Error(errors.join('\n'));
 await context.close();console.log('PASS '+width+' search, focus, picker bounds and draft');
}}finally{await browser.close();}
