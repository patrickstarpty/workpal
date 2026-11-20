import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createClient} from '../src/client.js';

const json=data=>new Response(JSON.stringify(data),{headers:{'Content-Type':'application/json'}});
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
const session=id=>({user:{id,username:id===1?'first':'latest'},workspaces:[{id:1,name:'Workpal',revision:1,role:'owner'}]});

test('accepts server catalog schemas with SQLite integer bounds without accepting unsafe business IDs',async()=>{
  const spec={action_id:'issue.read',schema:{type:'object',properties:{issue_id:{type:'integer',minimum:1,maximum:9223372036854775807}},required:['issue_id'],additionalProperties:false},
    output_schema:{type:'object',properties:{},required:[],additionalProperties:false},capability:'read',allowed_roles:['owner','admin','member'],
    authorization:'current membership and source grants',mutating:false,idempotency_required:false,confirmation_required:false,revision_required:false,compensation:'none'};
  const client=createClient({fetchImpl:async path=>{
    if(path.endsWith('/session'))return json(session(1));
    if(path.endsWith('/csrf'))return json({csrf_token:'token'});
    if(path.includes('actions?'))return json({actions:[spec]});
    return json({state:'completed',object_refs:[],data:{id:9007199254740992},error:null});
  }});
  await client.loadSession();client.selectWorkspace(1);
  const catalog=await client.catalog();
  assert.equal(catalog.actions[0].action_id,'issue.read');
  assert.ok(catalog.actions[0].schema.properties.issue_id.maximum>Number.MAX_SAFE_INTEGER);
  await assert.rejects(client.perform('issue.read',{issue_id:1}),e=>e.code==='invalid_response');
  await assert.rejects(client.perform('issue.read',{issue_id:9007199254740992}),e=>e.code==='invalid_input');
});

test('session refresh waiting behind an old login also waits for a newer queued login',async()=>{
  const entered=deferred(),release=deferred(),calls=[];let currentUser=1;
  const client=createClient({fetchImpl:async(path,options)=>{
    calls.push(path);
    if(path.endsWith('/csrf'))return json({csrf_token:'token'});
    if(path.endsWith('/login')) {
      const {username}=JSON.parse(options.body);
      if(username==='first'){entered.resolve();await release.promise;currentUser=1;}
      else currentUser=2;
      return json({user_id:currentUser});
    }
    return json(session(currentUser));
  }});
  const old=assert.rejects(client.login('first','transient'),e=>e.code==='context_changed');
  await entered.promise;
  const refreshing=client.loadSession().then(value=>({value}),error=>({error}));
  const latest=client.login('latest','transient').then(value=>({value}),error=>({error}));
  release.resolve();await old;
  const [fresh,loggedIn]=await Promise.all([refreshing,latest]);
  assert.equal(loggedIn.error,undefined,'A stale refresh must not cancel the latest login.');
  assert.equal(fresh.error,undefined);
  assert.equal(loggedIn.value.user.id,2);assert.equal(fresh.value.user.id,2);
  assert.equal(calls.filter(path=>path.endsWith('/login')).length,2);
});
