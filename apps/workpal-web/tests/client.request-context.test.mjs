import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createClient} from '../src/client.js';

const json=(value,status=200)=>new Response(JSON.stringify(value),{status});
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return{promise,resolve};};
async function harness(handler){
 const lost=[],calls=[];
 const client=createClient({onAccessLost:event=>lost.push(event),fetchImpl:async(path,options)=>{
  if(path.endsWith('/auth/session'))return json({user:{id:1,username:'reader'},workspaces:[{id:1,name:'First',revision:1,role:'member'}]});
  if(path.endsWith('/auth/csrf'))return json({csrf_token:'test-csrf'});
  calls.push(JSON.parse(options.body));return handler();
 }});
 await client.loadSession();client.selectWorkspace(1);return{client,lost,calls};
}

test('obsolete feature requests discard late bodies without reporting access loss in the current workspace',async()=>{
 for(const status of [200,403,404]){
  const ready=deferred(),response=deferred();let current=true,cancelled=false;
  const h=await harness(()=>{ready.resolve();return response.promise;});
  const checked=assert.rejects(h.client.perform('issue.read',{issue_id:1},{current:()=>current}),error=>error.code==='context_changed');
  await ready.promise;current=false;
  const body=new Response(new ReadableStream({cancel(){cancelled=true;}}),{status});
  body.json=()=>{throw Error('Obsolete body must not be parsed');};
  response.resolve(body);await checked;
  assert.equal(cancelled,true);assert.deepEqual(h.lost,[]);
  assert.deepEqual(h.calls,[{workspace_id:1,payload:{issue_id:1}}]);
 }
});

test('feature context is checked again after asynchronous response parsing',async()=>{
 for(const malformed of [false,true]){
  const parsing=deferred(),parsed=deferred();let current=true;
  const h=await harness(()=>{
   const response=json({},403);
   response.json=async()=>{parsing.resolve();await parsed.promise;if(malformed)throw Error('Invalid JSON');return{code:'permission_denied',message:'Old denial'};};
   return response;
  });
  const checked=assert.rejects(h.client.perform('issue.read',{issue_id:1},{current:()=>current}),error=>error.code==='context_changed');
  await parsing.promise;current=false;parsed.resolve();await checked;
  assert.deepEqual(h.lost,[]);
 }
});

test('current feature denials still notify, while obsolete requests do not dispatch',async()=>{
 const h=await harness(()=>json({code:'permission_denied',message:'Denied'},403));
 await assert.rejects(h.client.perform('issue.read',{issue_id:1},{current:()=>true}),error=>error.status===403);
 assert.deepEqual(h.lost,[{workspaceId:1,code:'permission_denied'}]);
 await assert.rejects(h.client.perform('issue.read',{issue_id:2},{current:()=>false}),error=>error.code==='context_changed');
 assert.equal(h.calls.length,1);
});
