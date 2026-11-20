import {withBrowser,signIn} from './browser-fixture.mjs';
import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
await withBrowser(async({base,newPage,runPython,expect,repo})=>{
 const seed=JSON.parse(runPython(`import json
from workpal.contracts import Actor
from workpal.work import service,issues,transitions
from workpal.workflows import service as workflows
a=Actor(1,1)
d=dict(states=[dict(key=k,label=l,category=c) for k,l,c in [('queue','Saved queue','backlog'),('ready','Ready <img src=x onerror=alert(1)>','todo'),('stuck','Waiting for owner','blocked'),('finished','Finished','done')]],transitions=[{'from':f,'to':t} for f,t in [('queue','ready'),('ready','stuck'),('stuck','ready')]],review_policy=dict(completion='manual',reviewer_roles=['owner']))
w=workflows.create(a,'History workflow',d)
v=workflows.publish(a,w['id'],w['revision'])
p=service.create(a,name='History project')
service.set_workflow(a,p['id'],v['id'],p['revision'])
i=issues.create(a,p['id'],'History issue',assignee_user_id=2)
empty=issues.create(a,p['id'],'Empty issue')
for n in range(26):
 target='ready' if n%2==0 else 'stuck'
 i=transitions.transition(a,i['id'],target,i['revision'],reason=('Reason '+str(n)+' <script>alert(1)</script> '+('long '*100)),blocked_owner_user_id=1 if target=='stuck' else 0)
print(json.dumps(dict(id=i['id'],events=transitions.list_transitions(a,i['id'],limit=100)['items'])))`).trim().split('\n').at(-1));
 const snapshot=()=>runPython(`import json
from django.db import connection
with connection.cursor() as c:
 tables=[t for t in connection.introspection.table_names() if any(x in t.lower() for x in ['issue','notification','outbox','idempotency','confirmation'])]
 result={}
 for t in tables:
  c.execute('SELECT * FROM "'+t+'" ORDER BY 1'); result[t]=c.fetchall()
 print(json.dumps(result,default=str,sort_keys=True))`).trim().split('\n').at(-1);
 const before=snapshot();
 const page=await newPage();await signIn(page,base,'reader');
 await page.getByLabel('Workspace',{exact:true}).selectOption('1');
 await page.getByRole('button',{name:'Issues',exact:true}).click();
 await page.getByRole('button',{name:`History issue (#${seed.id})`,exact:true}).click();
 const history=page.getByRole('region',{name:'Status history',exact:true});
 await expect(page.locator('.issue-detail')).toContainText('Blocked owner: owner (#1)');
 await expect(page.locator('.issue-detail')).toContainText('Assignee: reader (#2)');
 await page.context().setOffline(true);
 await page.getByRole('button',{name:'Show status history',exact:true}).click();
 await expect(history.getByRole('button',{name:'Retry',exact:true})).toBeVisible();
 await expect(history).not.toContainText('No status changes.');
 await page.context().setOffline(false);await history.getByRole('button',{name:'Retry',exact:true}).click();
 await expect(history.locator('details')).toHaveCount(20);
 await history.getByRole('button',{name:'Load more status history',exact:true}).click();
 await expect(history.locator('details')).toHaveCount(26);
 for(let n=0;n<26;n++)await expect(history.locator('summary').nth(n)).toContainText(seed.events[n].created_at);
 await history.locator('summary').last().focus();await page.keyboard.press('Enter');
 await expect(history.locator('details').last()).toContainText('Changed by: owner (#1)');
 await expect(history.locator('details').last()).toContainText(seed.events[25].reason);
 await expect(history.locator('script,img')).toHaveCount(0);
 await mkdir(`${repo}/outputs/workpal-web`,{recursive:true});
 await page.screenshot({path:`${repo}/outputs/workpal-web/a54c1-status-history-desktop.png`,fullPage:true});
 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:`${repo}/outputs/workpal-web/a54c1-status-history-mobile.png`,fullPage:true});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 await history.getByRole('button',{name:'Hide status history',exact:true}).click();
 await expect(history.locator('details')).toHaveCount(0);
 await history.getByRole('button',{name:'Show status history',exact:true}).click();
 await expect(history.locator('details')).toHaveCount(20);
 await page.getByRole('button',{name:'Empty issue (#2)',exact:true}).click();
 await page.getByRole('button',{name:'Show status history',exact:true}).click();
 await expect(page.getByRole('region',{name:'Status history',exact:true})).toContainText('No status changes.');
 assert.equal(snapshot(),before,'read-only database facts');
 console.log('status history real reads, 20+6, blocking facts, offline retry, keyboard, text safety, screenshots, SQL invariant passed');
});
