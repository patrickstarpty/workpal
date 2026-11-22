import {test} from 'node:test';
import assert from 'node:assert/strict';
import {openStore} from './store.mjs';
import {contribution,validateCommits} from './contribution.mjs';
import {createServer} from './api.mjs';
test('contribution uses explicit attribution, deduplicates shared commits, filters dates/projects and inherits squads',()=>{
 const store=openStore(':memory:');
 try{
  const issues=store.list('issues'),first=issues.find(i=>i.project_id=== 'TAP'),second=issues.find(i=>i.project_id==='Developer Platform');
  store.put('issues',{...first,assignee_type:'squad',assignee_id:'Review squad'});
  const c={repository:'local/repo',sha:'a',message:`${first.identifier} ${second.identifier}\nCo-authored-by: Workpal <workpal@users.noreply.github.com>`,at:'2026-11-20T23:30:00Z',additions:80,deletions:20,agentLines:40,humanLines:20};
  store.put('contribution_data',{id:'workspace',commits:[c,c,{...c,sha:'b',message:first.identifier,agentLines:0,humanLines:100}]});
  const params=new URLSearchParams('days=1&tz=Asia/Shanghai'),now=new Date('2026-11-21T01:00:00Z'),r=contribution(store,params,now);
  assert.equal(r.totals.commits,2);assert.equal(r.totals.agentLines,80);assert.equal(r.totals.humanLines,120);assert.equal(r.rows.length,2);assert.equal(r.rows.find(i=>i.id===first.id).team,'Review squad');assert.equal(r.daily[0].commits,2);
  params.set('project_id','Developer Platform');assert.equal(contribution(store,params,now).totals.commits,1);
  params.set('tz','UTC');assert.equal(contribution(store,params,now).totals.commits,0);
  assert.throws(()=>validateCommits([{...c,agentLines:200}]),/cannot exceed/);
 }finally{store.close();}
});
test('contribution import rejects invalid records without replacing saved data',async()=>{
 const server=createServer({dbPath:':memory:'});await new Promise(r=>server.listen(0,'127.0.0.1',r));
 try{
  const url=`http://127.0.0.1:${server.address().port}/api/dashboard/contribution`;
  const before=await(await fetch(url)).json();assert.ok(before.totals.commits>0);
  assert.equal((await fetch(url,{method:'PUT',body:JSON.stringify({commits:[{}]})})).status,400);
  assert.deepEqual(await(await fetch(url)).json(),before);
  assert.equal((await fetch(url,{method:'PUT',body:JSON.stringify({commits:[]})})).status,200);
  assert.equal((await(await fetch(url)).json()).totals.commits,0);
 }finally{await new Promise(r=>{server.close(r);server.closeAllConnections();});}
});
