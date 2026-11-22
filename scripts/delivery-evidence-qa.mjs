import {chromium, expect} from '@playwright/test';
const browser=await chromium.launch();
try {
 const page=await browser.newPage();
 await page.goto('http://127.0.0.1:4174');
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page.getByRole('button',{name:'Enter Workspace',exact:true})).toBeVisible();
 await page.evaluate(()=>{location.hash='/workpal-team/issues/workflow-work-10';});
 const evidence=page.getByRole('region',{name:'Delivery evidence'});
 await expect(evidence).toBeVisible();
 await expect(evidence.getByText(/Evidence pending/)).toBeVisible();
 await evidence.getByRole('button',{name:'Add deliverable'}).click();
 await evidence.getByLabel('Type',{exact:true}).selectOption('test');
 for(const name of ['method','results','failures','uncovered']) await expect(evidence.getByLabel(name,{exact:true})).toBeVisible();
 await page.setViewportSize({width:390,height:844});
 await page.getByRole('button',{name:'Toggle right sidebar',exact:true}).click();
 await expect(evidence).toBeVisible();
 await expect(evidence.getByRole('button',{name:'Add deliverable'})).toBeVisible();
 // No accidental submission of test evidence.
 await page.screenshot({path:'/tmp/workpal-evidence-mobile.png'});
 console.log('PASS existing ticket evidence pending; report fields and submission entry visible; no production records created');
} finally {await browser.close();}
