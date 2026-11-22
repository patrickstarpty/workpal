import assert from 'node:assert/strict';
import {expect} from '@playwright/test';
// Invoked by python-workspace-import-qa against an isolated imported SQLite.
export async function verify(page, base, fixture){

 const errors=[],channelRequests=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/\/api\/(lark|slack|dingtalk|wecom|telegram|weixin)/.test(r.url()))channelRequests.push(r.url());});
 const url=base+'/#/review/agents/Product%20partner?view=general';await page.goto(url);
 await page.getByRole('button',{name:'Change avatar',exact:true}).click();
 await page.getByRole('button',{name:'🦊',exact:true}).click();
 await expect(page.getByRole('button',{name:'Change avatar',exact:true})).toContainText('🦊');
 await page.reload();await expect(page.getByRole('button',{name:'Change avatar',exact:true})).toContainText('🦊');
 await page.locator('input[type=file][accept="image/*"]').setInputFiles('apps/web/public/icons/icon-192.png');
 
 await page.getByRole('button',{name:'Save',exact:true}).click();
 await expect(page.getByRole('button',{name:'Change avatar',exact:true}).locator('img')).toBeVisible();
 await page.reload();const img=page.getByRole('button',{name:'Change avatar',exact:true}).locator('img');await expect(img).toBeVisible();assert.ok(await img.evaluate(e=>e.naturalWidth>0));
 await page.goto(base+'/#/review/agents/Product%20partner');await expect(page.getByText('Microsoft Teams',{exact:true})).toBeVisible();
 await expect(page.getByText(/Status unavailable/)).toHaveCount(0);
 await page.goto(base+'/#/review/settings?tab=channels');await expect(page.getByText('Microsoft Teams',{exact:true})).toBeVisible();
 for(const name of ['Lark','Slack','DingTalk','WeCom','Telegram','WeChat'])await expect(page.getByText(name,{exact:true})).toHaveCount(0);
 assert.deepEqual(channelRequests,[]);assert.deepEqual(errors,[]);
 console.log('PASS: emoji and cropped image save/reload; agent and workspace show Teams only, no legacy channel requests');

}
