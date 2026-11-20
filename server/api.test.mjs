import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createServer} from './api.mjs';
test('HTTP CRUD persists across restart, validates input and rejects execution',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'workpal-original-'));let server;
 const start=async()=>{server=createServer({dbPath:join(dir,'db.sqlite')});await new Promise(r=>server.listen(0,'127.0.0.1',r));return `http://127.0.0.1:${server.address().port}`;};
 const stop=()=>new Promise(r=>{server.close(r);server.closeAllConnections();});
 try{
 let base=await start();const request=(path,method='GET',body)=>fetch(base+'/api/'+path,{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
 assert.equal((await request('bootstrap')).status,200);
 assert.equal((await request('projects','POST',{title:''})).status,400);
 assert.equal((await fetch(base+'/api/projects',{method:'POST',body:'{'})).status,400);
 const title='<img src=x onerror=alert(1)>';
 const response=await request('projects','POST',{title});assert.equal(response.status,201);const project=await response.json();assert.equal(project.title,title);
 assert.equal((await request('projects/'+project.id,'PATCH',{title:'Persisted project'})).status,200);
 await stop();base=await start();assert.equal((await (await request('projects/'+project.id)).json()).title,'Persisted project');
 assert.equal((await request('agents/any/run','POST',{})).status,501);
 assert.equal((await request('projects/'+project.id,'DELETE')).status,200);
 assert.equal((await request('projects/'+project.id)).status,404);
 await stop();base=await start();assert.equal((await request('projects/'+project.id)).status,404);
 }finally{if(server?.listening)await stop();await rm(dir,{recursive:true,force:true});}
});

test('repeated server shutdown closes SQLite only once',async()=>{
 const server=createServer({dbPath:':memory:'});
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 await new Promise(resolve=>server.close(resolve));
 await new Promise(resolve=>server.close(error=>{
  assert.equal(error?.code,'ERR_SERVER_NOT_RUNNING');resolve();
 }));
});

test('search and squad members use endpoint-specific response shapes',async()=>{
 const server=createServer({dbPath:':memory:'});await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const base=`http://127.0.0.1:${server.address().port}/api/`;
 try{
  const squads=await (await fetch(base+'squads')).json();
  const members=await (await fetch(base+'squads/'+encodeURIComponent(squads[0].id)+'/members')).json();
  assert.ok(members.length>0);for(const member of members){assert.equal(typeof member.member_id,'string');assert.ok(['member','agent'].includes(member.member_type));assert.equal(member.squad_id,squads[0].id);}
  assert.equal((await fetch(base+'squads/missing/members')).status,404);
  const result=await (await fetch(base+'issues/search?q=TAP-1022')).json();assert.ok(result.issues.some(row=>row.identifier==='TAP-1022'));assert.equal(result.issues[0].match_source,'title');
  assert.deepEqual(await (await fetch(base+'projects/search?q=never-match-123')).json(),{projects:[]});
 }finally{await new Promise(r=>{server.close(r);server.closeAllConnections();});}
});
