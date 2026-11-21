import {test} from 'node:test';
import assert from 'node:assert/strict';
import net from 'node:net';
import {assertFree, launch} from '../../scripts/python-web-dev.mjs';
test('occupied port is rejected without touching owner', async()=>{
 const s=net.createServer(); await new Promise(r=>s.listen(0,'127.0.0.1',r));
 try {await assert.rejects(assertFree(s.address().port), /occupied/); assert.ok(s.listening);} finally {s.close();}
});
test('migration failure propagates and prevents API startup',async()=>{
 await assert.rejects(launch({env:{...process.env,REDIS_URL:process.env.REDIS_URL||'redis://127.0.0.1:26379',WORKPAL_PORT:'24975',WORKPAL_WEB_PORT:'24974',WORKPAL_DATABASE_URL:'sqlite:////tmp/launcher-test.sqlite'},python:process.execPath,pythonArgs:['-e','process.exit(7)'],vite:[]}),/migration.*7/);
});
test('missing Python reports startup failure without a PID cleanup error',async()=>{
 await assert.rejects(launch({env:{...process.env,REDIS_URL:process.env.REDIS_URL||'redis://127.0.0.1:26379',WORKPAL_PORT:'24975',WORKPAL_WEB_PORT:'24974',WORKPAL_DATABASE_URL:'sqlite:////tmp/launcher-test.sqlite'},python:'/nonexistent/workpal-python'}),/Python migration failed/);
});
test('real launch serves health and releases both ports on SIGTERM',async()=>{
 const {spawn}=await import('node:child_process');
 const {mkdtemp}=await import('node:fs/promises');
 const {tmpdir}=await import('node:os');
 const {randomBytes}=await import('node:crypto');
 const dir=await mkdtemp(`${tmpdir()}/workpal-launcher-`);
 const c=spawn(process.execPath,['scripts/python-web-dev.mjs'],{env:{...process.env,REDIS_URL:process.env.REDIS_URL||'redis://127.0.0.1:26379',WORKPAL_PORT:'24985',WORKPAL_WEB_PORT:'24984',WORKPAL_DATABASE_URL:`sqlite:///${dir}/db.sqlite`,WORKPAL_UPLOAD_DIR:`${dir}/uploads`,REDIS_KEY_PREFIX:`workpal:test:${randomBytes(8).toString('hex')}:`,WORKPAL_DEV_AUTH:'true',AUTH_SECRET:randomBytes(32).toString('hex'),WORKPAL_HOST:'127.0.0.1',WORKPAL_ENV:'development'},stdio:'ignore'});
 const done=new Promise(r=>c.on('exit',r));
 try{
 let ready=false;
 for(let i=0;i<150;i++){try{if((await fetch('http://127.0.0.1:24984/')).ok){ready=true;break;}}catch{}await new Promise(r=>setTimeout(r,100));}
 assert.ok(ready,'real Python/Vite readiness');
 }finally{c.kill('SIGTERM');await done;}
 await assertFree(24985);await assertFree(24984);
});

for(const signal of ['SIGTERM','SIGINT'])test(`real worker schedules and launcher cleans up on ${signal}`,async()=>{
 const {spawn}=await import('node:child_process');
 const {mkdtemp,rm}=await import('node:fs/promises');
 const {tmpdir}=await import('node:os');
 const {randomBytes}=await import('node:crypto');
 const dir=await mkdtemp(`${tmpdir()}/workpal-worker-launcher-`);
 const c=spawn(process.execPath,['scripts/python-web-dev.mjs'],{env:{...process.env,REDIS_URL:'redis://127.0.0.1:26379',WORKPAL_PORT:'24995',WORKPAL_WEB_PORT:'24994',WORKPAL_DATABASE_URL:`sqlite:///${dir}/db.sqlite`,WORKPAL_UPLOAD_DIR:`${dir}/uploads`,REDIS_KEY_PREFIX:`workpal:test:${randomBytes(8).toString('hex')}:`,WORKPAL_ENV:'development',WORKPAL_HOST:'127.0.0.1'},stdio:'ignore'});
 const done=new Promise(r=>c.once('exit',r));
 try{
 let scheduled=false;
 for(let i=0;i<150;i++){
 const probe=spawn('python3',['-c',"import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); assert c.execute('select count(*) from scheduled_jobs').fetchone()[0]>0",`${dir}/db.sqlite`],{stdio:'ignore'});
 if(await new Promise(r=>probe.once('exit',code=>r(code===0)))){scheduled=true;break;}
 await new Promise(r=>setTimeout(r,100));
 }
 assert.ok(scheduled,'separate worker persists its schedule');
 }finally{c.kill(signal);await done;await rm(dir,{recursive:true,force:true});}
 await assertFree(24995);await assertFree(24994);
});

test('worker crash terminates API sibling',async()=>{
 const {mkdtemp,writeFile,rm}=await import('node:fs/promises');
 const {tmpdir}=await import('node:os');
 const dir=await mkdtemp(`${tmpdir()}/workpal-launcher-crash-`);
 const script=`const fs=require('fs');const command=process.argv[2];if(command==='migrate')process.exit(0);if(command==='worker')setTimeout(()=>process.exit(9),500);else setInterval(()=>{},1000);`;
 await writeFile(`${dir}/fake.cjs`,script);
 try{
 await assert.rejects(launch({env:{...process.env,REDIS_URL:process.env.REDIS_URL||'redis://127.0.0.1:26379',WORKPAL_DATABASE_URL:`sqlite:///${dir}/db`,WORKPAL_PORT:'24975',WORKPAL_WEB_PORT:'24974'},python:process.execPath,pythonArgs:[`${dir}/fake.cjs`],vite:[]}),/exited/);
 }finally{await rm(dir,{recursive:true,force:true});}
});

for (const ignoreTerm of [false, true]) test(`exited worker descendants are cleaned up (ignore TERM: ${ignoreTerm})`, async()=>{
 const {mkdtemp,writeFile,readFile,rm}=await import('node:fs/promises');
 const {tmpdir}=await import('node:os');
 const dir=await mkdtemp(`${tmpdir()}/workpal-descendant-`);
 let pid;
 const descendant=`${ignoreTerm ? "process.on('SIGTERM',()=>{});" : ''}require('fs').writeFileSync(${JSON.stringify(`${dir}/pid`)},String(process.pid));setInterval(()=>{},1000);`;
 const script=`const fs=require('fs');const command=process.argv[2];if(command==='migrate')process.exit(0);if(command==='worker'){require('child_process').spawn(process.execPath,['-e',${JSON.stringify(descendant)}],{stdio:'ignore'});const t=setInterval(()=>{if(fs.existsSync(${JSON.stringify(`${dir}/pid`)}))process.exit(9);},10);}else setInterval(()=>{},1000);`;
 await writeFile(`${dir}/fake.cjs`,script);
 try {
  await assert.rejects(launch({env:{...process.env,REDIS_URL:process.env.REDIS_URL||'redis://127.0.0.1:26379',WORKPAL_DATABASE_URL:`sqlite:///${dir}/db`,WORKPAL_PORT:'24975',WORKPAL_WEB_PORT:'24974'},python:process.execPath,pythonArgs:[`${dir}/fake.cjs`],vite:[]}),/exited/);
  pid=Number(await readFile(`${dir}/pid`,'utf8'));
  let alive=true;
  for(let i=0;i<100;i++){try{process.kill(pid,0);}catch(e){if(e.code==='ESRCH'){alive=false;break;}throw e;}await new Promise(r=>setTimeout(r,20));}
  assert.equal(alive,false,'descendant must exit before cleanup completes');
 } finally {
  if(pid)try{process.kill(pid,'SIGKILL');}catch(e){if(e.code!=='ESRCH')throw e;}
  await rm(dir,{recursive:true,force:true});
 }
});

test('real production serves frontend and API and releases port on SIGTERM',async()=>{
 const {spawn}=await import('node:child_process');
 const {mkdtemp}=await import('node:fs/promises');
 const {tmpdir}=await import('node:os');
 const {randomBytes}=await import('node:crypto');
 const dir=await mkdtemp(`${tmpdir()}/workpal-launcher-`);
 const c=spawn(process.execPath,['scripts/workpal-start.mjs'],{env:{...process.env,REDIS_URL:process.env.REDIS_URL||'redis://127.0.0.1:26379',WORKPAL_PORT:'25085',WORKPAL_WEB_PORT:'25084',WORKPAL_DATABASE_URL:`sqlite:///${dir}/db.sqlite`,WORKPAL_UPLOAD_DIR:`${dir}/uploads`,REDIS_KEY_PREFIX:`workpal:test:${randomBytes(8).toString('hex')}:`,WORKPAL_DEV_AUTH:'true',AUTH_SECRET:randomBytes(32).toString('hex'),WORKPAL_HOST:'127.0.0.1',WORKPAL_ENV:'development'},stdio:'ignore'});
 const done=new Promise(r=>c.on('exit',r));
 try{
 let ready=false;
 for(let i=0;i<150;i++){try{if((await fetch('http://127.0.0.1:25085/')).ok){ready=true;break;}}catch{}await new Promise(r=>setTimeout(r,100));}
 assert.ok(ready,'real Python frontend readiness');
 assert.equal((await fetch('http://127.0.0.1:25085/healthz')).status,200);
 assert.equal((await fetch('http://127.0.0.1:25085/api/nonexistent')).status,404);
 }finally{c.kill('SIGTERM');await done;}
 await assertFree(25085);await assertFree(25084);
});

for(const failed of ['serve','readiness'])test(`${failed} failure cleans up siblings`,async()=>{
 const {mkdtemp,writeFile,rm}=await import('node:fs/promises');
 const {tmpdir}=await import('node:os');
 const dir=await mkdtemp(`${tmpdir()}/workpal-failure-`);
 await writeFile(`${dir}/fake.cjs`, `const cmd=process.argv[2];if(cmd==='migrate')process.exit(0);if(cmd===${JSON.stringify(failed)})process.exit(8);setInterval(()=>{},1000);`);
 try{await assert.rejects(launch({env:{...process.env,REDIS_URL:'redis://127.0.0.1:26379',WORKPAL_DATABASE_URL:`sqlite:///${dir}/db`,WORKPAL_PORT:'25185',WORKPAL_WEB_PORT:'25184'},python:process.execPath,pythonArgs:[`${dir}/fake.cjs`],readinessTimeout:200}),failed==='serve'?/exited/:/readiness/);}finally{await rm(dir,{recursive:true,force:true});}
});
test('unavailable Redis prevents real application readiness',async()=>{
 const {mkdtemp,rm}=await import('node:fs/promises');
 const {tmpdir}=await import('node:os');
 const dir=await mkdtemp(`${tmpdir()}/workpal-no-redis-`);
 try{await assert.rejects(launch({mode:'production',env:{...process.env,WORKPAL_ENV:'development',WORKPAL_HOST:'127.0.0.1',WORKPAL_DATABASE_URL:`sqlite:///${dir}/db`,WORKPAL_UPLOAD_DIR:`${dir}/uploads`,REDIS_URL:'redis://127.0.0.1:1',REDIS_KEY_PREFIX:'workpal:unavailable-test:',WORKPAL_PORT:'25285'},readinessTimeout:1500}),/exited|readiness/);}finally{await rm(dir,{recursive:true,force:true});}
 await assertFree(25285);
});
