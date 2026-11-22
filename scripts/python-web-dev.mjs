import {spawn} from 'node:child_process';
import net from 'node:net';
import {existsSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const root=fileURLToPath(new URL('../',import.meta.url));
export async function assertFree(port){
 await new Promise((resolve,reject)=>{const s=net.createServer();s.once('error',()=>reject(new Error(`Port ${port} occupied; stop its owner or configure WORKPAL_PORT/WORKPAL_WEB_PORT`)));s.listen(port,'127.0.0.1',()=>s.close(resolve));});
}
export async function launch({mode='development',frontendDir=path.join(root,'apps/web/dist'),env=process.env,python=path.join(root,'server/.venv/bin/python'),pythonArgs=['-m','workpal_backend.cli'],readinessTimeout=20000,vite=[process.execPath,path.join(root,'node_modules/vite/bin/vite.js'),'--mode','python']}={}){
 if(!env.WORKPAL_DATABASE_URL) throw new Error('Set WORKPAL_DATABASE_URL to an isolated Python SQLite database; launcher explicitly migrates it');
 if(mode==='production'&&!existsSync(path.join(frontendDir,'index.html')))throw new Error('Frontend build missing; run npm run build first');
 if(!env.REDIS_URL)throw new Error('Set REDIS_URL explicitly');
 const api=Number(env.WORKPAL_PORT||(mode==='production'?4174:4175)), web=Number(env.WORKPAL_WEB_PORT||4174);
 for(const port of (mode==='production'?[api]:[api,web])) {if(!Number.isInteger(port)||port<1||port>65535)throw new Error('Invalid launcher port');await assertFree(port);}
 if(mode!=='production'&&api===web)throw new Error('API and web ports must differ');
 const childEnv={...env,WORKPAL_PORT:String(api),WORKPAL_WEB_PORT:String(web),FRONTEND_ORIGIN:env.FRONTEND_ORIGIN||`http://127.0.0.1:${mode==='production'?api:web}`};
 const children=[];let stopping=false;
 const start=(command,args,cwd=root)=>{const c=spawn(command,args,{cwd,env:childEnv,stdio:'inherit',detached:true});children.push(c);c.done=new Promise(resolve=>{c.once('error',()=>{c.finished=true;resolve(1);});c.once('exit',(code,signal)=>{c.finished=true;resolve(code??(signal?1:0));});});return c;};
 const kill=(c,signal)=>{if(!Number.isInteger(c.pid))return;try{process.kill(-c.pid,signal);}catch(e){if(e.code!=='ESRCH')throw e;}};
 let stopPromise;
 const groupExists=c=>{
  if(!Number.isInteger(c.pid))return false;
  try{process.kill(-c.pid,0);return true;}catch(e){if(e.code==='ESRCH'||e.code==='EPERM')return false;throw e;}
 };
 const stop=()=>{
  if(stopPromise)return stopPromise;
  stopping=true;
  stopPromise=(async()=>{
   // Direct children can exit while their process groups still own descendants.
   const owned=children.filter(c=>Number.isInteger(c.pid));
   owned.forEach(c=>kill(c,'SIGTERM'));
   const deadline=Date.now()+4000;
   while(owned.some(groupExists)&&Date.now()<deadline){
    await new Promise(resolve=>setTimeout(resolve,25));
   }
   owned.filter(groupExists).forEach(c=>kill(c,'SIGKILL'));
   await Promise.all(children.map(c=>c.done));
  })();
  return stopPromise;
 };
 let interrupted;
 const onSignal=()=>{interrupted=true;void stop();};
 process.on('SIGINT',onSignal);process.on('SIGTERM',onSignal);
 try{
 const migration=start(python,[...pythonArgs,'migrate']);const code=await migration.done;
 if(code||interrupted)throw new Error(`Python migration failed (exit ${code}); check venv and isolated database settings`);
 if(stopping)throw new Error('Python launcher interrupted');
 const worker=start(python,[...pythonArgs,'worker']);
 const backend=start(python,[...pythonArgs,'serve',...(mode==='production'?['--frontend-dir',frontendDir]:[])]);
 const deadline=Date.now()+readinessTimeout;
 while(true){
 const exited=await Promise.race([worker.done.then(code=>({code})),backend.done.then(code=>({code})),new Promise(r=>setTimeout(()=>r(null),100))]);
 if(exited)throw new Error(`Python API exited (${exited.code}); inspect startup output`);
 try{const response=await fetch(`http://127.0.0.1:${api}/healthz`,{signal:AbortSignal.timeout(500)});if(response.ok)break;}catch{}
 if(stopping||Date.now()>deadline)throw new Error('Python API readiness timed out; check Redis and configuration');
 }
 if(stopping)throw new Error('Python launcher interrupted');
 if(mode==='production'){
 const result=await Promise.race([worker.done,backend.done]);
 if(!interrupted)throw new Error(`Python child exited unexpectedly (${result})`);
 return;
 }
 const frontend=start(vite[0],[...vite.slice(1),'--port',String(web),'--strictPort'],path.join(root,'apps/web'));
 const result=await Promise.race([worker.done,backend.done,frontend.done]);
 if(!interrupted)throw new Error(`Python web child exited unexpectedly (${result})`);
 }finally{await stop();process.removeListener('SIGINT',onSignal);process.removeListener('SIGTERM',onSignal);}
}
if(process.argv[1]===fileURLToPath(import.meta.url))launch().catch(error=>{console.error(error.message);process.exitCode=1;});
