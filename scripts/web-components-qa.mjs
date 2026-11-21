import assert from 'node:assert/strict';
import {expect} from '@playwright/test';
// Invoked by python-workspace-import-qa against an isolated imported SQLite.
export async function verify(page, base, fixture){

 const errors=[];
 page.on('pageerror',error=>errors.push(error.message));
 const go=async path=>{await page.goto(`${base}/#/review/${path}`);await expect(page.getByRole('button',{name:'Switch workspace'})).toBeVisible();};
 await go('projects');
 await page.getByRole('button',{name:'Search...',exact:true}).click();
 await expect(page.getByRole('dialog',{name:'Command bar'})).toBeVisible();
 await page.getByRole('combobox').fill('TAP-1022');
 const hit=page.getByRole('option').filter({hasText:'TAP-1022'}).first();await expect(hit).toBeVisible();await hit.click();
 await expect(page).toHaveURL(/issues\/TAP-1022/);
 await page.keyboard.press('Meta+k');await expect(page.getByRole('dialog',{name:'Command bar'})).toBeVisible();await page.keyboard.press('Escape');
 await expect(page.getByRole('dialog',{name:'Command bar'})).toHaveCount(0);
 await page.getByRole('button',{name:'Ask Workpal',exact:true}).click();
 await expect(page.getByRole('button',{name:'Minimize',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Minimize',exact:true}).click();
 await expect(page.getByRole('button',{name:'Minimize',exact:true})).toHaveCount(0);
 await page.keyboard.press('Meta+j');await expect(page.getByRole('button',{name:'Minimize',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Minimize',exact:true}).click();
 await go('projects');
 await page.getByRole('button',{name:'New Issue',exact:true}).click();
 await expect(page.getByRole('dialog')).toBeVisible();await page.keyboard.press('Escape');
 await page.getByRole('button',{name:'New project',exact:true}).last().click();
 await expect(page.getByRole('dialog')).toBeVisible();await page.keyboard.press('Escape');
 console.log('PASS: chat shortcut and issue/project creation dialogs');
 console.log('PASS: search click, result navigation, keyboard open/close; Ask Workpal open/minimize');
 await go('agents');
 await page.getByRole('link',{name:/^Skills/}).click();await expect(page).toHaveURL(/\/skills$/);
 await page.getByText(fixture.skills[0].name,{exact:true}).first().click();
 await expect(page).toHaveURL(new RegExp('/skills/'+fixture.skills[0].id+'$'));
 await expect(page.locator('[data-page-error]')).toHaveCount(0);
 await expect(page.getByText(fixture.skills[0].name,{exact:true}).first()).toBeVisible();
 await page.getByRole('link',{name:'Analytics',exact:true}).click();await expect(page).toHaveURL(/\/usage$/);
 await expect(page.getByText('Leaderboard',{exact:true})).toBeVisible();
 console.log('PASS: Resources → Skills → skill detail; Analytics navigation');
 await go('squads');await page.getByRole('button',{name:'My squads',exact:true}).click();await page.getByRole('menuitemradio',{name:/All squads/}).click();await page.getByText(fixture.squads[0].name,{exact:true}).first().click();
 await expect(page).toHaveURL(/\/squads\//);
 await expect(page.getByText('Unknown member',{exact:true})).toHaveCount(0);
 await expect(page.getByText(fixture.squads[0].leader_id,{exact:true}).first()).toBeVisible();
 await expect(page.locator('[data-page-error]')).toHaveCount(0);
 console.log('PASS: squad detail and real member identities');
 for(const route of ['projects','issues','agents','skills','squads','autopilots','inbox','chat','settings','usage','runtimes','my-issues','views','agents/new']){
  await go(route);await page.waitForTimeout(250);await expect(page.locator('[data-page-error]')).toHaveCount(0);await expect(page.getByText('Page unavailable',{exact:true})).toHaveCount(0);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1),false,route);
 }
 await go('missing-page');await expect(page.getByText('Page unavailable',{exact:true})).toBeVisible();
 assert.deepEqual(errors,[]);console.log('PASS: 14 desktop web routes, no page exceptions or horizontal document overflow; unknown route is explicit');

}
