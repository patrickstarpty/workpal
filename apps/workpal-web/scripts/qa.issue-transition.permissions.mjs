import assert from 'node:assert/strict';
import {withBrowser,signIn} from './browser-fixture.mjs';
await withBrowser(async({base,newPage,runPython,expect,repo})=>{
 const py=c=>JSON.parse(runPython(c).trim().split('\n').at(-1));
 const seed=()=>py(`import json
from workpal.contracts import Actor,ObjectRef
from workpal.work import service,issues,transitions
from workpal.access.service import register_object
from workpal.access.models import SourceGrant,RegisteredObject
from django.contrib.auth import get_user_model
from workpal.identity.models import Membership
a=Actor(1,1);p=service.create(a,'Permission checks');u=get_user_model().objects.create_user(username='candidate'+str(p['id']));Membership.objects.create(user=u,workspace_id=1,role='member');i=issues.create(a,p['id'],'Permission '+str(p['id']));i=transitions.transition(a,i['id'],'todo',i['revision'])
for kind,ref in [('issue',issues.ref(i['id'])),('requirements',issues.requirement_ref(i['requirements_version_id']))]:
 s=ObjectRef('source',kind+str(i['id']));register_object(1,s,is_source=True);register_object(1,ref,[s]);row=RegisteredObject.objects.get(kind=s.kind,object_id=s.id)
 for uid in [1,u.pk]:SourceGrant.objects.create(user_id=uid,source=row,read=True,write=True)
print(json.dumps(dict(item=i,uid=u.pk,name=u.username)))`);
 const state=id=>py(`import json
from workpal.work.models import Issue,IssueTransition,IssueRequirements
from workpal.collaboration.models import Notification
from workpal.audit.models import AuditEvent,Outbox
from workpal.actions.models import IdempotencyResult
print(json.dumps(dict(issue=Issue.objects.values().get(pk=${id}),history=list(IssueTransition.objects.filter(issue_id=${id}).values()),requirements=list(IssueRequirements.objects.filter(issue_id=${id}).values()),notifications=list(Notification.objects.filter(issue_id=${id}).values()),audit=AuditEvent.objects.filter(action_id='issue.transition',fields__issue_id=${id}).count(),outbox=Outbox.objects.filter(action_id='issue.transition',event__fields__issue_id=${id}).count(),cache=IdempotencyResult.objects.filter(action_id='issue.transition',result__data__id=${id}).count()),default=str))`);
 async function open(s,target='in_progress'){const p=await newPage();p.setDefaultTimeout(7000);await signIn(p,base);await p.getByLabel('Workspace',{exact:true}).selectOption('1');await p.getByRole('button',{name:'Issues',exact:true}).click();await p.getByLabel('Search issues').fill(s.item.title);await p.getByRole('button',{name:`${s.item.title} (#${s.item.id})`,exact:true}).click();await p.getByRole('button',{name:'Change status',exact:true}).click();const d=p.getByRole('dialog');await d.getByLabel('Target status',{exact:true}).selectOption(target);if(target==='blocked'){await d.getByLabel('Reason',{exact:true}).fill('Waiting');await d.getByLabel('Search people').fill(s.name);await d.getByRole('button',{name:`${s.name} (#${s.uid})`,exact:true}).click();}return {p,d};}
 const revoke=(s,kind,uid,field)=>runPython(`from workpal.access.models import SourceGrant;SourceGrant.objects.filter(user_id=${uid},source__object_id='${kind}${s.item.id}').update(${field}=False)`);
 async function submit(p,d,label='Save status'){const response=p.waitForResponse(r=>r.url().endsWith('/actions/issue.transition'));await d.getByRole('button',{name:label,exact:true}).click();return (await response).status();}
 // Independent authorized controls exercise both ordinary and Blocked transitions.
 for(const target of ['in_progress','blocked']){const s=seed(),{p,d}=await open(s,target),before=state(s.item.id);if(target==='blocked'){assert.equal(await d.getByText('Assignee',{exact:true}).count(),0);for(const [name,width] of [['desktop',1440],['mobile',390]]){await p.setViewportSize({width,height:1000});assert(await d.evaluate(n=>n.scrollWidth<=n.clientWidth));await p.screenshot({path:repo+`/outputs/workpal-web/a54c2-permissions-${name}.png`});}}assert.equal(await submit(p,d),200);await expect(d).toHaveCount(0);assert.equal(state(s.item.id).history.length,before.history.length+1);}
 for(const kind of ['issue','requirements'])for(const field of ['read','write']){const s=seed(),{p,d}=await open(s),before=state(s.item.id);revoke(s,kind,1,field);const status=await submit(p,d);if(kind==='requirements'&&field==='write'){assert.equal(status,200);await expect(d).toHaveCount(0);}else{assert.equal(status,403);await expect(d).toHaveCount(0);await expect(p.locator('.issue-detail')).toHaveCount(0);assert.deepEqual(state(s.item.id),before);}}
 console.log('PASS 1 requester source revocation and write-only requirements control');
 for(const mode of ['membership','inactive','issue','requirements']){const s=seed(),{p,d}=await open(s,'blocked'),before=state(s.item.id);if(mode==='membership')runPython(`from workpal.identity.models import Membership;Membership.objects.filter(user_id=${s.uid}).delete()`);else if(mode==='inactive')runPython(`from django.contrib.auth import get_user_model;get_user_model().objects.filter(pk=${s.uid}).update(is_active=False)`);else revoke(s,mode,s.uid,'read');assert.equal(await submit(p,d),mode==='membership'||mode==='inactive'?404:403);await expect(d).toHaveCount(0);assert.deepEqual(state(s.item.id),before);}
 console.log('PASS 2 selected Blocked owner revocation preserves all business facts');
 for(const kind of ['issue','requirements']){const s=seed(),{p,d}=await open(s),before=state(s.item.id),attempts=[];await p.route('**/api/v1/actions/issue.transition',async r=>{attempts.push(r.request().postDataJSON());if(attempts.length===1){assert.equal((await r.fetch()).status(),200);return r.abort('failed');}return r.continue();});await d.getByRole('button',{name:'Save status',exact:true}).click();await expect(d.getByRole('button',{name:'Retry original request',exact:true})).toBeEnabled();const committed=state(s.item.id);assert.equal(committed.history.length,before.history.length+1);revoke(s,kind,1,'read');assert.equal(await submit(p,d,'Retry original request'),403);await expect(d).toHaveCount(0);await expect(p.locator('.issue-detail')).toHaveCount(0);assert.deepEqual(attempts[0],attempts[1]);assert.deepEqual(state(s.item.id),committed);}
 console.log('PASS 3 real committed lost responses reject restricted cached retries');
});
