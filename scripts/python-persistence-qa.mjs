import assert from 'node:assert/strict';
import {spawn,execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {mkdtemp,open,rm,symlink,cp,readFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {randomBytes,createHash} from 'node:crypto';
import {DatabaseSync} from 'node:sqlite';
import {chromium,expect} from '@playwright/test';


expect.setTimeout?.(20000);
const run=promisify(execFile);
const live=false;
const state=await mkdtemp(join(tmpdir(),'workpal-persistence-'));
const base=live||'http://127.0.0.1:24374';
const env={...process.env,PYTHONPATH:resolve('server/src'),
 WORKPAL_DATABASE_URL:`sqlite:///${join(state,'python.sqlite')}`,
 WORKPAL_UPLOAD_DIR:join(state,'uploads'),WORKPAL_PORT:'24374',WORKPAL_WEB_PORT:'24374',
 WORKPAL_HOST:'127.0.0.1',WORKPAL_ENV:'development',WORKPAL_DEV_AUTH:'true',
 AUTH_SECRET:randomBytes(32).toString('hex'),
 REDIS_URL:'redis://127.0.0.1:26379',
 REDIS_KEY_PREFIX:`workpal:import-qa:${randomBytes(12).toString('hex')}:`};
const rollback=process.env.WORKPAL_ROLLBACK_SHA;
let runtime=process.cwd();
let child,browser,log,exited,passed=false;
const digest=async p=>createHash('sha256').update(await readFile(p)).digest('hex');
let sourceDigest;
if(rollback){
 const sha=(await run('git',['rev-parse',rollback+'^{commit}'])).stdout.trim();
 const snapshot=join(state,'snapshot');await run('mkdir',['-p',snapshot]);
 const archive=join(state,'snapshot.tar');await run('git',['archive','--output',archive,sha]);
 await run('tar',['-xf',archive,'-C',snapshot]);
 await symlink(resolve('node_modules'),join(snapshot,'node_modules'));
 await symlink(resolve('server/.venv'),join(snapshot,'server/.venv'));
 await cp(resolve('apps/web/dist'),join(snapshot,'apps/web/dist'),{recursive:true});
 console.log('IMMUTABLE SNAPSHOT',sha,snapshot,'build index sha256',await digest(join(snapshot,'apps/web/dist/index.html')));
 runtime=snapshot;
}

async function start(cwd=process.cwd()){
 child=spawn('npm',['start'],{cwd,env:{...env,PYTHONPATH:join(cwd,'server/src')},detached:true,stdio:['ignore',log.fd,log.fd]});
 exited=new Promise(resolve=>child.once('exit',resolve));
 for(let i=0;i<450;i++){
  if(child.exitCode!==null)throw Error(`Server exited: ${state}`);
  try{if((await fetch(base+'/healthz')).ok)return;}catch{}
  await new Promise(r=>setTimeout(r,100));
 }
 throw Error(`Readiness timeout: ${state}`);
}
async function stop(){if(child){process.kill(-child.pid,'SIGTERM');await exited;child=null;}}
try{
 await run('server/.venv/bin/python',['-c','import sqlite3,sys; s=sqlite3.connect("file:"+sys.argv[1]+"?mode=ro",uri=True); t=sqlite3.connect(sys.argv[2]); s.backup(t); t.close(); s.close()',resolve('server/data/workpal.sqlite'),join(state,'legacy.sqlite')]);
 log=await open(join(state,'service.log'),'w');
 sourceDigest=await digest(join(state,'legacy.sqlite'));
 await start();

 browser=await chromium.launch();
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 page.setDefaultTimeout(15000);
 await page.goto(base+'/#/home');
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await run('server/.venv/bin/python',['-m','workpal_backend.cli','import-legacy','--source',join(state,'legacy.sqlite'),'--owner-email','workpal@fwd.com'],{env});
 await page.getByRole('button',{name:'Enter Workspace',exact:true}).click();
 await expect(page).toHaveURL(/#\/review\/issues$/);
 
 await page.locator('[data-action=new-issue]').click(); await page.getByRole('button',{name:'Switch to Manual',exact:true}).click();
 await page.locator('[role=dialog] [contenteditable=true]').first().fill('Persistence QA '+Date.now());
 
 const created=page.waitForResponse(r=>r.url().endsWith('/api/issues')&&r.request().method()==='POST'); created.catch(()=>{});
 await page.getByRole('button',{name:'Create Issue',exact:true}).click();
 const result=await created;assert.equal(result.status(),201);const issue=await result.json();
 await page.goto(base+'/#/review/issues/'+issue.id);
 await expect(page.getByText(issue.title,{exact:true})).toBeVisible();
 const description='Persisted description '+issue.id;
 const patch=page.waitForResponse(r=>r.url().endsWith('/issues/'+issue.id)&&r.request().method()==='PUT'&&r.request().postDataJSON()?.description===description);
 await page.locator('[contenteditable=true]').filter({has:page.locator('[data-placeholder="Add description..."]')}).fill(description);
 await page.getByText(issue.title,{exact:true}).click();
 assert.ok((await patch).ok());
 await page.getByRole('button',{name:'Leave a comment...',exact:true}).click();
 const comment='Persistence comment '+issue.id;
 const composer=page.locator('[contenteditable=true]').filter({has:page.locator('[data-placeholder="Leave a comment..."]')});
 await composer.fill(comment);
 const posted=page.waitForResponse(r=>r.url().endsWith('/comments')&&r.request().method()==='POST'); posted.catch(()=>{});
 await page.locator('[contenteditable=true].ProseMirror-focused').press('Meta+Enter');
 const pr=await posted; assert.ok(pr.ok()); await expect(page.getByText(comment,{exact:true})).toBeVisible();
 await page.goto(base+'/#/review/issues/'+issue.id);await page.reload();
 await expect(page.getByText(description,{exact:true})).toBeVisible();
 await expect(page.getByText(comment,{exact:true})).toBeVisible();
 const cookies=await page.context().cookies(base);
 const csrf=cookies.find(c=>c.name==='workpal_csrf_session').value;
 const headers={'X-Workspace-Slug':'review','X-CSRF-Token':csrf};
 // Delete a separate imported task through the product HTTP endpoint.
 const deletedId='TAP-029';
 const old=await page.request.get(base+'/api/issues/'+deletedId,{headers});assert.ok(old.ok());
 const deleted=await old.json();
 assert.ok((await page.request.delete(base+'/api/issues/'+deleted.id,{headers})).ok());
 async function verify(){
  await page.goto(base+'/#/review/issues/'+issue.id);await page.reload();
  await expect(page.getByText(issue.title,{exact:true})).toBeVisible().catch(async e=>{console.log(page.url(),await page.locator('body').innerText());throw e;});
  await expect(page.getByText(description,{exact:true})).toBeVisible();
  await expect(page.getByText(comment,{exact:true})).toBeVisible();
  assert.equal((await page.request.get(base+'/api/issues/'+deleted.id,{headers})).status(),404);
  await page.goto(base+'/#/review/issues/'+deleted.id);await page.reload();
  await expect(page.getByText('Issue not found',{exact:true})).toBeVisible();
 }
 await verify();console.log('PASS before restart',issue.id,deleted.id);
 await stop();await start(runtime);
 await page.goto(base+'/#/home');await page.reload();
 if(await page.getByRole('button',{name:'Sign in',exact:true}).isVisible())await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await page.getByRole('button',{name:'Enter Workspace',exact:true}).click();
 headers['X-CSRF-Token']=(await page.context().cookies(base)).find(c=>c.name==='workpal_csrf_session').value;
 await verify();
 console.log('PASS after same-database restart',issue.id,deleted.id);
 const next='Snapshot write '+issue.id;
 assert.ok((await page.request.put(base+'/api/issues/'+issue.id,{headers,data:{description:next}})).ok());
 const reread=await (await page.request.get(base+'/api/issues/'+issue.id,{headers})).json();
 assert.equal(reread.description,next);
 await stop();
 const db=new DatabaseSync(join(state,'python.sqlite'),{readOnly:true});
 console.log('SAME DATABASE',join(state,'python.sqlite'),'schema',db.prepare('select version_num from alembic_version').all(),'record',issue.id,'description',reread.description);
 db.close();
 assert.equal(await digest(join(state,'legacy.sqlite')),sourceDigest);
 console.log('PASS snapshot continued write; legacy sha256 unchanged',sourceDigest);




 passed=true;
}finally{
 await browser?.close();await stop();await log?.close();
 console.log(`QA artifacts: ${state}`);
}
