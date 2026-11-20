import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createClient} from '../src/client.js';
test('loads actual session through same origin transport',async()=>{
 const c=createClient({fetchImpl:async(path,options)=>{
 assert.equal(path,'/api/v1/auth/session'); assert.equal(options.credentials,'same-origin');
 return new Response(JSON.stringify({user:{id:1,username:'user'},workspaces:[]}),{headers:{'Content-Type':'application/json'}});
 }}); assert.equal((await c.loadSession()).user.id,1);
});
