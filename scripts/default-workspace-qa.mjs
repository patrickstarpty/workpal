import {chromium,expect} from '@playwright/test';
const browser=await chromium.launch();
try {
 const page=await browser.newPage();await page.goto('http://127.0.0.1:4174');
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await page.getByRole('button',{name:'Enter Workspace',exact:true}).click();
 await expect(page).toHaveURL(/#\/workpal-team\/issues$/);
 await page.getByRole('button',{name:'Switch workspace',exact:true}).click();
 await page.getByRole('menuitem',{name:/TAP/}).click();
 await expect(page).toHaveURL(/#\/review\/issues$/);
 await expect(page.getByRole('button',{name:'Switch workspace',exact:true})).toBeVisible();
 await page.reload();
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await page.evaluate(()=>{location.hash='/home';});
 await page.getByRole('button',{name:'Enter Workspace',exact:true}).click();
 await expect(page).toHaveURL(/#\/review\/issues$/);
 await page.getByRole('button',{name:'Switch workspace',exact:true}).click();
 await page.getByRole('menuitem',{name:/SMART/}).click();
 await expect(page).toHaveURL(/#\/workpal-team\/issues$/);
 console.log('PASS: SMART first entry, switch to TAP, persisted after reload, switch back to SMART');
} finally {await browser.close();}
