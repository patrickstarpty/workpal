import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createClient, ClientError} from '../src/client.js';

const context = {user:{id:7,username:'patrick'},workspaces:[
  {id:1,name:'One',revision:1,role:'owner'}, {id:2,name:'Two',revision:1,role:'member'}]};
const result = (data={}, state='completed') => ({state,object_refs:[],data,error:null});
const json = (data,status=200) => new Response(JSON.stringify(data), {status,headers:{'Content-Type':'application/json'}});
const deferred = () => {let resolve; const promise=new Promise(r=>resolve=r);return {promise,resolve};};
function harness(initial=context) {
  const calls=[],lost=[],routes=new Map();
  routes.set('/api/v1/auth/session',()=>json(initial));
  routes.set('/api/v1/auth/csrf',()=>json({csrf_token:'csrf-initial'}));
  const client=createClient({onAccessLost:event=>lost.push(event),fetchImpl:async(path,options)=>{
    calls.push({path,options});
    return routes.has(path)?routes.get(path)(options):json(result());
  }});
  return {client,calls,lost,routes};
}
async function selected() {const h=harness();await h.client.loadSession();h.client.selectWorkspace(1);return h;}

test('maps action payload, exact retry key, revision and confirmation using same origin credentials',async()=>{
  const {client,calls}=await selected();
  const payload={issue_id:42,title:'<script>text</script>'};
  assert.deepEqual(await client.perform('issue.update',payload,{revision:3,key:'same-key',confirmationId:'confirmed'}),result());
  const last=calls.at(-1);
  assert.equal(last.path,'/api/v1/actions/issue.update');
  assert.deepEqual(JSON.parse(last.options.body),{workspace_id:1,payload,expected_revision:3,idempotency_key:'same-key',confirmation_id:'confirmed'});
  assert.equal(last.options.headers['X-CSRFToken'],'csrf-initial');
  for(const call of calls) {
    assert.equal(call.options.credentials,'same-origin'); assert.equal(call.options.mode,'same-origin');
    assert.equal(call.options.cache,'no-store'); assert.equal(call.options.redirect,'error');
    assert.ok(call.path.startsWith('/api/v1/'));
  }
});

test('refreshes CSRF after login before returning the real session',async()=>{
  const {client,calls,routes}=harness();let count=0;
  routes.set('/api/v1/auth/csrf',()=>json({csrf_token:++count===1?'before-login':'after-login'}));
  routes.set('/api/v1/auth/login',options=>{
    assert.equal(options.headers['X-CSRFToken'],'before-login');
    assert.deepEqual(JSON.parse(options.body),{username:'patrick',password:'transient-password'});
    return json({user_id:7});
  });
  assert.deepEqual(await client.login('patrick','transient-password'),context);
  client.selectWorkspace(1);await client.perform('workspace.read',{});
  assert.equal(calls.at(-1).options.headers['X-CSRFToken'],'after-login');
  assert.deepEqual(calls.slice(0,4).map(c=>c.path),['/api/v1/auth/csrf','/api/v1/auth/login','/api/v1/auth/csrf','/api/v1/auth/session']);
  assert.equal(calls.filter(c=>c.options.body?.includes('transient-password')).length,1);
});

test('waiting confirmation is returned intact and never automatically consumed',async()=>{
  const {client,calls,routes}=await selected();
  const waiting=result({confirmation_id:'human-token'},'waiting_confirmation');
  routes.set('/api/v1/actions/member.revoke',()=>json(waiting));
  assert.deepEqual(await client.perform('member.revoke',{membership_id:2},{revision:1,key:'intent'}),waiting);
  assert.equal(calls.filter(c=>c.path.endsWith('/member.revoke')).length,1);
  await client.perform('member.revoke',{membership_id:2},{revision:1,key:'intent',confirmationId:'human-token'});
  assert.equal(JSON.parse(calls.at(-1).options.body).idempotency_key,'intent');
});

test('409 preserves form input and 403 signals source invalidation without retrying',async()=>{
  const {client,calls,lost,routes}=await selected();
  const payload={title:'Unsent revision',criteria:[{key:'one',text:'Keep input'}]};
  const saved=structuredClone(payload);
  routes.set('/api/v1/actions/issue.update',()=>json({code:'revision_conflict',message:'Reload.',request_id:'request-1',retryable:false,details:{}},409));
  await assert.rejects(client.perform('issue.update',payload,{revision:1,key:'intent'}),e=>e instanceof ClientError&&e.status===409&&e.code==='revision_conflict'&&e.requestId==='request-1'&&e.outcome==='failed');
  assert.deepEqual(payload,saved);assert.deepEqual(lost,[]);
  routes.set('/api/v1/actions/issue.update',()=>json({code:'permission_denied',message:'Denied.',request_id:'request-2',retryable:false,details:{}},403));
  await assert.rejects(client.perform('issue.update',payload,{revision:1,key:'intent'}),e=>e.status===403);
  assert.deepEqual(lost,[{workspaceId:1,code:'permission_denied'}]);
  assert.equal(calls.filter(c=>c.path.endsWith('/issue.update')).length,2);
});

test('network failure is unknown, never a completed write or automatic retry',async()=>{
  const {client,calls,routes}=await selected();
  routes.set('/api/v1/actions/issue.create',()=>{throw new TypeError('network detail');});
  await assert.rejects(client.perform('issue.create',{title:'Keep this'},{key:'intent'}),e=>e instanceof ClientError&&e.outcome==='unknown'&&e.status===0&&!e.message.includes('network detail'));
  assert.equal(calls.filter(c=>c.path.endsWith('/issue.create')).length,1);
});

test('session copies cannot authorize unlisted workspaces or mutate internal choices',async()=>{
  const {client}=harness();const session=await client.loadSession();
  session.workspaces.push({id:99,name:'Forged',revision:1,role:'owner'});
  session.workspaces[0].name='Mutated';
  assert.throws(()=>client.selectWorkspace(99),ClientError);
  const selected=client.selectWorkspace(1);assert.equal(selected.name,'One');selected.name='Another mutation';
  assert.equal(client.selectWorkspace(1).name,'One');
});

test('workspace switch discards late data and late permission errors from the former context',async()=>{
  for(const status of [200,403]) {
    const {client,lost,routes}=await selected();const started=deferred(),release=deferred();
    routes.set('/api/v1/actions/issue.read',()=>{started.resolve();return release.promise;});
    const pending=client.perform('issue.read',{issue_id:1});const checked=assert.rejects(pending,e=>e instanceof ClientError&&e.code==='context_changed');
    await started.promise;client.selectWorkspace(2);
    release.resolve(status===200?json(result({title:'Old private title'})):json({code:'permission_denied',message:'Old denial'},403));
    await checked;assert.deepEqual(lost,[]);
  }
});

test('captures payload before waiting for CSRF, without mutating the caller form',async()=>{
  const {client,calls,routes}=await selected();const started=deferred(),release=deferred();
  routes.set('/api/v1/auth/csrf',()=>{started.resolve();return release.promise;});
  const payload={title:'Original',criteria:[{key:'one',text:'Original'}]};
  const pending=client.perform('issue.create',payload,{key:'intent'});await started.promise;
  payload.title='Later';payload.criteria[0].text='Later';
  release.resolve(json({csrf_token:'fresh'}));await pending;
  assert.deepEqual(JSON.parse(calls.at(-1).options.body).payload,{title:'Original',criteria:[{key:'one',text:'Original'}]});
  assert.equal(payload.title,'Later');
});

test('changed membership on session refresh invalidates old requests and removes the workspace choice',async()=>{
  const {client,routes}=await selected();const started=deferred(),release=deferred();
  routes.set('/api/v1/actions/issue.read',()=>{started.resolve();return release.promise;});
  const pending=client.perform('issue.read',{issue_id:1});const checked=assert.rejects(pending,ClientError);
  await started.promise;routes.set('/api/v1/auth/session',()=>json({...context,workspaces:[]}));
  await client.loadSession();release.resolve(json(result({title:'Old data'})));await checked;
  assert.throws(()=>client.selectWorkspace(1),ClientError);
});

test('rejects malformed or unsafe session protocols before creating trusted context',async()=>{
  for(const invalid of [[],{}, {user:'wrong',workspaces:context.workspaces},
    {...context,user:{id:7,username:'patrick',password:'not-allowed'}},
    {...context,workspaces:[{id:'1',name:'One',revision:1,role:'owner'}]},
    {...context,workspaces:[{id:1,name:'One',revision:1,role:'superuser'}]},
    {...context,workspaces:[context.workspaces[0],context.workspaces[0]]},
    {...context,workspaces:[{id:9007199254740992,name:'Unsafe',revision:1,role:'owner'}]}]) {
    const {client}=harness(invalid);
    await assert.rejects(client.loadSession(),e=>e instanceof ClientError&&e.code==='invalid_response'&&e.outcome==='unknown');
    assert.throws(()=>client.selectWorkspace(1),ClientError);
  }
});

test('does not expose malformed action responses as successful results',async()=>{
  for(const invalid of [[],{}, {state:'completed'}, result({},'invented'),
    {...result(),object_refs:[{kind:'issue',id:1}]}, {...result(),data:[]},
    result({id:9007199254740992})]) {
    const {client,routes}=await selected();routes.set('/api/v1/actions/issue.read',()=>json(invalid));
    await assert.rejects(client.perform('issue.read',{issue_id:1}),e=>e instanceof ClientError&&e.code==='invalid_response'&&e.outcome==='unknown');
  }
});

test('malformed catalog and login success responses are not accepted',async()=>{
  const {client,routes}=await selected();routes.set('/api/v1/actions?workspace_id=1',()=>json({actions:'not-a-list'}));
  await assert.rejects(client.catalog(),e=>e.code==='invalid_response');
  routes.set('/api/v1/auth/login',()=>json({}));
  await assert.rejects(client.login('patrick','transient'),e=>e.code==='invalid_response'&&e.outcome==='unknown');
});

test('even a malformed current 403 response invalidates source data',async()=>{
  const {client,lost,routes}=await selected();
  routes.set('/api/v1/actions/issue.read',()=>new Response('Not JSON',{status:403}));
  await assert.rejects(client.perform('issue.read',{issue_id:1}),ClientError);
  assert.deepEqual(lost,[{workspaceId:1,code:'invalid_response'}]);
});

test('logout invalidates the context even when the server outcome is unknown',async()=>{
  const {client,routes}=await selected();
  routes.set('/api/v1/auth/logout',()=>{throw new Error('offline');});
  await assert.rejects(client.logout(),e=>e instanceof ClientError&&e.outcome==='unknown');
  await assert.rejects(client.perform('workspace.read',{}),e=>e.code==='workspace_required');
});

test('serializes cookie-changing authentication so a slow login cannot undo a later logout',async()=>{
  const {client,calls,routes}=harness();const started=deferred(),release=deferred();
  let tokenNumber=0,logoutToken;
  routes.set('/api/v1/auth/csrf',()=>json({csrf_token:'token-'+(++tokenNumber)}));
  routes.set('/api/v1/auth/login',()=>{started.resolve();return release.promise;});
  routes.set('/api/v1/auth/logout',options=>{
    logoutToken=options.headers['X-CSRFToken'];
    return json({state:'completed'});
  });
  const login=client.login('patrick','transient');const oldLogin=assert.rejects(login,e=>e.code==='context_changed');
  await started.promise;const logout=client.logout().then(value=>({value}),error=>({error}));
  await Promise.resolve();await Promise.resolve();
  const earlyRequests=calls.filter(c=>c.path==='/api/v1/auth/logout').length;
  release.resolve(json({user_id:7}));await oldLogin;const outcome=await logout;
  assert.equal(earlyRequests,0,'Do not race cookie-changing requests.');
  assert.equal(outcome.error,undefined);assert.deepEqual(outcome.value,{state:'completed'});
  assert.notEqual(logoutToken,'token-1','Login rotates the server CSRF token.');
  assert.throws(()=>client.selectWorkspace(1),ClientError);
});

test('rejects unsafe or non-JSON request data before sending anything',async()=>{
  const {client,calls}=await selected();const cycle={};cycle.self=cycle;
  for(const value of [NaN,Infinity,undefined,1n,9007199254740992,cycle,new Date()]) {
    const count=calls.length;
    await assert.rejects(client.perform('issue.create',{title:value},{key:'intent'}),e=>e.code==='invalid_input');
    assert.equal(calls.length,count);
  }
});
