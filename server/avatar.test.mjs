import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm,readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createServer} from './api.mjs';
test('avatar upload and agent selection persist across restart; reject non-images',async()=>{
 const dir=await mkdtemp(join(tmpdir(),'workpal-avatar-'));let server;
 const start=async()=>{server=createServer({dbPath:join(dir,'test.sqlite')});await new Promise(r=>server.listen(0,'127.0.0.1',r));return `http://127.0.0.1:${server.address().port}`;};
 const stop=()=>new Promise(r=>{server.close(r);server.closeAllConnections();});
 try{
  let base=await start();const bytes=await readFile('apps/web/public/icons/icon-192.png');
  const form=new FormData();form.set('file',new Blob([bytes],{type:'image/png'}),'avatar.png');
  const upload=await fetch(base+'/api/upload-file',{method:'POST',body:form});assert.equal(upload.status,201);const image=await upload.json();
  const agent='/api/agents/Product%20partner';assert.equal((await fetch(base+agent,{method:'PUT',body:JSON.stringify({avatar_url:image.url})})).status,200);
  await stop();base=await start();assert.equal((await(await fetch(base+agent)).json()).avatar_url,image.url);
  const saved=await fetch(base+image.url);assert.equal(saved.headers.get('content-type'),'image/png');assert.deepEqual(Buffer.from(await saved.arrayBuffer()),bytes);
  const bad=new FormData();bad.set('file',new Blob(['<script>alert(1)</script>'],{type:'image/png'}),'avatar.png');assert.equal((await fetch(base+'/api/upload-file',{method:'POST',body:bad})).status,415);
 }finally{if(server?.listening)await stop();await rm(dir,{recursive:true,force:true});}
});
