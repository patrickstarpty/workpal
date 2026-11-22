import assert from 'node:assert/strict';
import {expect} from '@playwright/test';
// Invoked by python-workspace-import-qa against an isolated imported SQLite.
export async function verify(page, base, fixture){

 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/#/review/usage');
 await expect(page.getByRole('tab')).toHaveText(['Usage','Contribution','Errors']);
 await page.getByRole('tab',{name:'Contribution',exact:true}).click();await expect(page).toHaveURL(/tab=contribution/);
 await expect(page.getByText('Contribution by ticket',{exact:true})).toBeVisible();await expect(page.getByText('Daily contribution',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Period',exact:true}).click();
 const range=page.waitForResponse(r=>r.url().includes('/api/dashboard/contribution?')&&r.url().includes('days=7'));
 await page.getByRole('menuitemradio',{name:'7d',exact:true}).click();const data=await(await range).json();assert.ok(data.totals.commits>0);
 await page.getByRole('button',{name:'Project',exact:true}).click();
 const project=page.waitForResponse(r=>r.url().includes('/api/dashboard/contribution?')&&r.url().includes('project_id='));
 await page.getByRole('menuitemradio',{name:'Developer Platform',exact:true}).click();const scoped=await(await project).json();assert.ok(scoped.totals.commits>0&&scoped.totals.commits<data.totals.commits);
 await page.getByRole('region',{name:'Ticket contribution',exact:true}).getByRole('button').first().click();await expect(page).toHaveURL(/issues\//);
 await page.goto(base+'/#/review/usage?tab=contribution');await expect(page.getByRole('tab',{name:'Contribution',exact:true})).toHaveAttribute('aria-selected','true');
 await page.getByText('Attribution rules & import',{exact:true}).click();
 const commit={repository:'local/repo',sha:'e2e',message:'TAP-029 Small follow-up',at:new Date().toISOString(),additions:25,deletions:5,agentLines:12,humanLines:18};
 await page.getByLabel('Import commit data',{exact:true}).setInputFiles({name:'commits.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify([commit]))});
 await expect(page.getByRole('status').filter({hasText:'Imported 1 commit records.'})).toBeVisible();await page.reload();
 await expect(page.getByRole('region',{name:'Ticket contribution',exact:true}).getByRole('button')).toHaveCount(1);
 await page.getByRole('button',{name:'Account',exact:true}).click();
 await expect(page.getByRole('menuitem',{name:/Discord|Desktop app/})).toHaveCount(0);
 await expect(page.getByRole('menuitem',{name:/Docs/})).toHaveAttribute('href',/127\.0\.0\.1:4000\/docs/);
 await page.keyboard.press('Escape');await page.goto(base+'/#/review/changelog');await expect(page.getByRole('heading',{name:'Changelog',exact:true})).toBeVisible();
 await page.setViewportSize({width:390,height:844});await page.goto(base+'/#/review/usage?tab=contribution');await expect(page.getByText('Contribution by ticket',{exact:true})).toBeVisible();
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false);
 assert.deepEqual(errors,[]);console.log('PASS: second tab, deep link, charts, period/project filters, ticket navigation, JSON import/reload, menu links and narrow layout');

}
