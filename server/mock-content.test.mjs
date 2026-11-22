import {test} from 'node:test';
import assert from 'node:assert/strict';
import {openStore} from './store.mjs';
import {dashboardRows} from './mock-content.mjs';
import {fixture,originalIssues} from './fixtures.mjs';
import {DatabaseSync} from 'node:sqlite';
import {mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
const sum=(rows,key)=>rows.reduce((n,r)=>n+(r[key]||0),0);
test('dashboard rollups reconcile across metrics, agents, projects and ranges',()=>{
 const store=openStore(':memory:');
 try {
  const get=(route,params='days=30&tz=Asia%2FShanghai')=>dashboardRows(store,'/api/dashboard/'+route,new URLSearchParams(params));
  const daily=get('usage/daily'),agents=get('usage/by-agent'),runtime=get('runtime/daily'),failures=get('failures/daily');
  assert.ok(daily.length>20);
  for(const field of ['input_tokens','output_tokens','cache_read_tokens','cache_write_tokens','task_count'])assert.equal(sum(daily,field),sum(agents,field));
  assert.equal(sum(daily,'task_count'),sum(runtime,'task_count'));
  assert.equal(sum(runtime,'task_count'),sum(failures,'task_count'));
  assert.equal(sum(runtime,'failed_count'),sum(failures.filter(r=>r.failure_reason),'task_count'));
  assert.ok(sum(get('usage/daily','days=7'),'task_count')<sum(daily,'task_count'));
  assert.equal(fixture.projects.reduce((n,p)=>n+sum(get('usage/daily','days=30&tz=Asia%2FShanghai&project_id='+encodeURIComponent(p.id)),'task_count'),0),sum(daily,'task_count'));
  assert.deepEqual(get('usage/daily','project_id=missing'),[]);
  assert.ok(new Set(runtime.map(r=>r.task_count)).size>5);
 }finally{store.close();}
});
test('content migration preserves user edits and deleted tickets and runs only once',()=>{
 const dir=mkdtempSync(join(tmpdir(),'workpal-mock-')),path=join(dir,'db.sqlite');
 try {
  let store=openStore(path);const id='TAP-029',other='TAP-028';
  store.put('issues',{...store.get('issues',id),description:'My own notes'});store.remove('issues',other);store.close();
  const db=new DatabaseSync(path);db.exec("DELETE FROM meta WHERE key='rich-mock-v1'; DELETE FROM records WHERE kind IN ('comments','analytics_runs')");
  const original=originalIssues.find(i=>i.id==='TAP-033');db.prepare("UPDATE records SET body=? WHERE kind='issues' AND id=?").run(JSON.stringify(original),original.id);db.close();
  store=openStore(path);assert.equal(store.get('issues',id).description,'My own notes');assert.equal(store.get('issues',other),null);
  assert.match(store.get('issues','TAP-033').description,/Decision needed/);
  assert.ok(store.list('comments').every(c=>c.issue_id!==other));
  const count=store.list('analytics_runs').length;store.close();store=openStore(path);assert.equal(store.list('analytics_runs').length,count);store.close();
 }finally{rmSync(dir,{recursive:true,force:true});}
});
