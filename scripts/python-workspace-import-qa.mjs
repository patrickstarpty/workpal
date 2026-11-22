import assert from 'node:assert/strict';
import {spawn,execFile} from 'node:child_process';
import {promisify} from 'node:util';
import {mkdtemp,open,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {randomBytes} from 'node:crypto';
import {DatabaseSync} from 'node:sqlite';
import {chromium,expect} from '@playwright/test';


const run=promisify(execFile);
const live=process.env.WORKPAL_QA_URL;
const state=await mkdtemp(join(tmpdir(),'workpal-import-browser-'));
const base=live||'http://127.0.0.1:24274';
const env={...process.env,PYTHONPATH:resolve('server/src'),
 WORKPAL_DATABASE_URL:`sqlite:///${join(state,'python.sqlite')}`,
 WORKPAL_UPLOAD_DIR:join(state,'uploads'),WORKPAL_PORT:'24275',WORKPAL_WEB_PORT:'24274',
 WORKPAL_HOST:'127.0.0.1',WORKPAL_ENV:'development',WORKPAL_DEV_AUTH:'true',
 AUTH_SECRET:randomBytes(32).toString('hex'),
 REDIS_URL:process.env.REDIS_URL||'redis://127.0.0.1:26379',
 REDIS_KEY_PREFIX:`workpal:import-qa:${randomBytes(12).toString('hex')}:`};
let child,browser,log,exited,passed=false;
try{
 if(!live){
  // SQLite backup includes committed WAL content; the real source is read-only.
  // No Node mock initialization or seed execution is allowed here.
  await run('server/.venv/bin/python',['-c',
   'import sqlite3,sys; source=sqlite3.connect("file:"+sys.argv[1]+"?mode=ro",uri=True); target=sqlite3.connect(sys.argv[2]); source.backup(target); target.close(); source.close()',
   resolve('server/data/workpal.sqlite'),join(state,'legacy.sqlite')]);
  log=await open(join(state,'service.log'),'w');
  child=spawn(process.execPath,['scripts/python-web-dev.mjs'],{env,stdio:['ignore',log.fd,log.fd]});
  exited=new Promise(resolve=>child.once('exit',(code)=>resolve(code)));
  const deadline=Date.now()+45000;
  while(true){
   if(child.exitCode!==null)throw Error(`QA server exited; inspect ${state}/service.log`);
   try{if((await fetch(base,{signal:AbortSignal.timeout(500)})).ok)break;}catch{}
   if(Date.now()>deadline)throw Error(`QA server readiness timed out; inspect ${state}/service.log`);
   await new Promise(resolve=>setTimeout(resolve,200));
  }
 }
 const source=new DatabaseSync(live?resolve('server/data/workpal.sqlite'):join(state,'legacy.sqlite'),{readOnly:true});
 const counts=Object.fromEntries(source.prepare('SELECT kind,count(*) AS count FROM records GROUP BY kind').all().map(row=>[row.kind,row.count]));
 source.close();
 browser=await chromium.launch();
 const page=await browser.newPage({viewport:{width:1440,height:1000}});
 const errors=[];
 page.on('pageerror',error=>errors.push(error.message));
 await page.goto(base+'/#/home');
 await expect(page.getByLabel('Email',{exact:true})).toHaveValue('workpal@fwd.com');
 await expect(page.getByLabel('Verification code')).toHaveCount(0);
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page.getByRole('button',{name:'Enter Workspace',exact:true})).toBeVisible();
 if(!live){
  await page.getByRole('button',{name:'Enter Workspace',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Choose a workspace'})).toBeVisible();
  const args=['-m','workpal_backend.cli','import-legacy','--source',join(state,'legacy.sqlite'),'--owner-email','workpal@fwd.com'];
  await run('server/.venv/bin/python',[...args,'--dry-run'],{env});
  assert.deepEqual(await (await page.request.get(base+'/api/workspaces')).json(),[]);
  await run('server/.venv/bin/python',args,{env});
  await run('server/.venv/bin/python',args,{env});
  await page.goto(base+'/#/home');await page.reload();
 }
 await page.getByRole('button',{name:'Enter Workspace',exact:true}).click();
 await expect(page).toHaveURL(/#\/review\/issues$/);
 await expect(page.getByRole('button', {name: 'Switch workspace', exact: true})).toBeVisible();
 await expect(page.getByRole('heading',{name:'Choose a workspace'})).toHaveCount(0);
 await expect(page.getByText('Developer Platform',{exact:true}).first()).toBeVisible();
 const headers={'X-Workspace-Slug':'review'};
 const request=path=>page.request.get(base+'/api/'+path,{headers});
 const projects=await request('projects');assert.equal(projects.status(),200);
 assert.equal((await projects.json()).projects.length,counts.projects);
 const issues=await request('issues');assert.equal(issues.status(),200);
 assert.equal((await issues.json()).total,counts.issues);
 for(const [kind,count] of [['agents',counts.agents],['skills',counts.skills],['squads',counts.squads],['runtimes',counts.runtimes],['chat/sessions',counts.sessions]]){
  const result=await request(kind);assert.equal(result.status(),200,kind);
  assert.equal((await result.json()).length,count,kind);
 }
 await page.reload();
 await expect(page.getByText('Developer Platform',{exact:true}).first()).toBeVisible();
 await page.goto(base+'/#/review/issues/TAP-029');
 await expect(page.getByText('Cases to cover',{exact:true})).toBeVisible();
 await expect(page.getByText('Please include a scanned PDF as well; a text-only fixture will miss the OCR path.',{exact:true})).toBeVisible();
 await page.goto(base+'/#/review/usage');
 await expect(page.getByText('Leaderboard',{exact:true})).toBeVisible();
 await expect(page.getByText('No usage yet',{exact:true})).toHaveCount(0);
 const usage=await request('dashboard/usage/daily?days=90');assert.equal(usage.status(),200);
 assert.ok((await usage.json()).length>0);
 const contribution=await request('dashboard/contribution?days=30');assert.equal(contribution.status(),200);
 await page.goto(base+'/#/home');
 await expect(page.getByRole('button',{name:'Enter Workspace',exact:true})).toBeVisible();
 await page.setViewportSize({width:390,height:844});
 await page.getByRole('button',{name:'Enter Workspace',exact:true}).click();
 await page.locator('[data-sidebar=trigger]').click();
 await expect(page.getByRole('button', {name: 'Switch workspace', exact: true})).toBeVisible();
 await page.keyboard.press('Escape');
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
 await page.setViewportSize({width:1440,height:1000});
 const fixture={skills:await (await request('skills')).json(),squads:await (await request('squads')).json()};
 for(const name of ['avatar-channels','web-components','mock-data','contribution']){
  console.log('RUN Python product QA:',name);
  const extra=await browser.newPage({viewport:{width:1440,height:1000}});
  await extra.context().addCookies(await page.context().cookies());
  extra.setDefaultTimeout(10000);
  await (await import(`./${name}-qa.mjs`)).verify(extra,base,fixture);
  await extra.close();
 }
 await page.getByRole('button',{name:'Account',exact:true}).click();
 const logout=page.waitForResponse(response=>response.url().endsWith('/auth/logout')&&response.request().method()==='POST');
 await page.getByRole('menuitem',{name:'Log out',exact:true}).click();
 assert.equal((await logout).status(),200);
 await expect(page.getByRole('button',{name:'Sign in',exact:true})).toBeVisible();
 await page.reload();
 await expect(page.getByRole('button',{name:'Sign in',exact:true})).toBeVisible();
 assert.equal((await request('projects')).status(),401);
 assert.deepEqual(errors,[]);
 passed=true;
 console.log('PASS: Python import, default login → capabilities → TAP, original projects/tasks/comments/skills/squads/analytics, reload, narrow layout and logout');
}finally{
 await browser?.close();
 if(child){child.kill('SIGTERM');await exited;}
 await log?.close();
 if(!passed)console.error(`QA artifacts: ${state}`);
 else await rm(state,{recursive:true,force:true});
}
