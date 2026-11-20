import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createClient} from '../src/client.js';
const json=d=>new Response(JSON.stringify(d));
function setup(){
 let release,started;const ready=new Promise(r=>started=r),gate=new Promise(r=>release=r);const calls=[];
 const client=createClient({fetchImpl:async(path,options)=>{
  calls.push(path);
  if(path.endsWith('/csrf'))return json({csrf_token:'token'});
  if(path.endsWith('/login')){const {username}=JSON.parse(options.body);if(username==='first'){started();await gate;}return json({user_id:1});}
  return json({user:{id:1,username:'latest'},workspaces:[]});
 }});return {client,calls,ready,release:()=>release()};
}
test('overlapping logins settle the old cookie request before sending the latest intent',async()=>{
 const h=setup();const first=assert.rejects(h.client.login('first','secret'),e=>e.code==='context_changed');await h.ready;
 const skipped=assert.rejects(h.client.login('skipped','secret'),e=>e.code==='context_changed');
 const latest=h.client.login('latest','secret');assert.equal(h.calls.filter(p=>p.endsWith('/login')).length,1);
 h.release();await first;await skipped;assert.equal((await latest).user.username,'latest');
 assert.equal(h.calls.filter(p=>p.endsWith('/login')).length,2);
});
test('ordinary session refresh waits for authentication to settle',async()=>{
 const h=setup();const login=h.client.login('first','secret');await h.ready;
 const session=h.client.loadSession();await Promise.resolve();assert.equal(h.calls.filter(p=>p.endsWith('/session')).length,0);
 h.release();await login;assert.equal((await session).user.username,'latest');
 assert.equal(h.calls.filter(p=>p.endsWith('/session')).length,2);
});
