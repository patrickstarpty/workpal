import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {randomUUID} from 'node:crypto';
function workspace(){
  const values=new Map();
  const localStorage={get length(){return values.size;},key:i=>[...values.keys()][i],getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value)};
  const ctx=vm.createContext({localStorage,crypto:{randomUUID}});
  for(const name of ['data','workspace-fixtures','model','analytics-data'])vm.runInContext(readFileSync(new URL('../src/'+name+'.js',import.meta.url),'utf8'),ctx);
  return ctx;
}
test('linked workspace has complete ticket, run, delivery, contribution and usage references',()=>{
  const ctx=workspace(),studio=ctx.WorkpalStudio,db=studio.db;
  const tasks=db.tasks.filter(t=>t.fixtureSource==='linked-v2');
  assert.ok(tasks.length>=70);
  assert.equal(new Set(tasks.map(t=>t.status)).size,6);
  for(const task of tasks){assert.ok(db.tasks.some(p=>p.id===task.parent));assert.ok(db.projects.includes(task.project));}
  for(const run of db.runs.filter(r=>r.fixtureSource)){assert.ok(db.tasks.some(t=>t.id===run.task));assert.equal(run.context.harness,'Copilot CLI');assert.ok(db.agents.some(a=>a.name===run.agent));}
  for(const delivery of db.deliveries.filter(d=>d.fixtureSource)){
    const task=db.tasks.find(t=>t.id===delivery.task),run=db.runs.find(r=>r.id===delivery.run);
    if(delivery.disposition==='current')assert.equal(task.currentDeliveryId,delivery.id);assert.equal(run.deliveryId,delivery.id);
    if(task.status==='review'&&delivery.disposition==='current')assert.equal(studio.approvalEligibility(delivery),'');
  }
  for(const commit of db.contributionCommits){assert.ok(db.tasks.some(t=>t.id===commit.task));if(commit.run)assert.ok(db.runs.some(r=>r.id===commit.run&&r.task===commit.task));}
  for(const record of db.analyticsHistory.records)assert.ok(db.runs.some(r=>r.id===record.run&&r.task===record.task&&r.status==='finished'));
  const totals=ctx.WorkpalAnalyticsData.contribution(db,{days:365}).totals;
  assert.equal(totals.commits,db.contributionCommits.length);assert.ok(totals.human>0&&totals.workpal>0);
  console.log(JSON.stringify({tasks:tasks.length,runs:db.runs.filter(r=>r.fixtureSource).length,deliveries:db.deliveries.filter(d=>d.fixtureSource).length,commits:totals.commits,reports:db.reports.length}));
});
test('fixture upgrade is idempotent and preserves authored imports and notes',()=>{
  const ctx=workspace(),db=ctx.WorkpalStudio.db;
  db.notes.push({text:'Keep my review'});const before=JSON.stringify(db);
  assert.equal(ctx.WorkpalWorkspaceFixtures(db),false);assert.equal(JSON.stringify(db),before);
  const other=JSON.parse(before);delete other.linkedFixtureVersion;
  other.tasks=[];other.runs=[];other.deliveries=[];other.reports=[];
  other.contributionCommits=[];other.analyticsHistory={source:'import',records:[]};
  ctx.WorkpalWorkspaceFixtures(other);assert.equal(other.contributionCommits.length,0);assert.equal(other.analyticsHistory.source,'import');assert.equal(other.notes.at(-1).text,'Keep my review');
  assert.ok(db.agents.every(a=>a.runtime==='Copilot CLI'));
});

test('scenario history has coherent timestamps, dependencies and returned revisions',()=>{
  const ctx=workspace(),db=ctx.WorkpalStudio.db;
  assert.ok(db.deliveries.some(d=>d.version===2));
  for(const d of db.deliveries.filter(d=>d.fixtureSource)){
    const run=db.runs.find(r=>r.id===d.run);
    assert.ok(run.inputSnapshot.capturedAt<=d.createdAt);
    assert.ok(d.createdAt<=Date.now());
    if(d.supersedes){const prior=db.deliveries.find(p=>p.id===d.supersedes);assert.equal(prior.task,d.task);assert.equal(prior.review.decision,'return');assert.ok(prior.review.at<d.createdAt);}
    for(const c of db.contributionCommits.filter(c=>c.run===run.id))assert.ok(c.at<=d.createdAt);
  }
  for(const t of db.tasks.filter(t=>t.dependsOn))for(const id of t.dependsOn)assert.ok(db.tasks.some(p=>p.id===id&&p.id!==t.id));
  assert.ok(new Set(db.contributionCommits.map(c=>c.sha.slice(0,12))).size===db.contributionCommits.length);
});

test('annual history spans the year, reconciles attribution and preserves imports during upgrade',()=>{
  const ctx=workspace(),db=ctx.WorkpalStudio.db,api=ctx.WorkpalAnalyticsData;
  const annual=db.contributionCommits.filter(c=>c.fixtureSource==='annual-v1');
  assert.ok(new Set(annual.map(c=>new Date(c.at).toISOString().slice(0,7))).size>=12);
  for(const c of annual)assert.equal(c.agentLines+c.humanLines,c.additions+c.deletions);
  const result=api.contribution(db,{days:365}),calendar=api.contributionCalendar(result,365);
  assert.equal(calendar.length,365);assert.equal(calendar.reduce((n,d)=>n+d.commits,0),result.totals.commits);
  assert.ok(api.snapshot(db,{days:365}).totals.failed>0);
  const before=JSON.stringify(db);ctx.WorkpalWorkspaceFixtures(db,Date.now()+86400000);assert.equal(JSON.stringify(db),before);
  const imported=JSON.parse(before);delete imported.annualFixtureVersion;
  imported.contributionCommits=[];imported.analyticsHistory={source:'import',records:[]};
  ctx.WorkpalWorkspaceFixtures(imported);assert.equal(imported.contributionCommits.length,0);assert.equal(imported.analyticsHistory.records.length,0);
  const skill=api.skillUsage(db).find(r=>r.total>0);assert.ok(skill);assert.equal(skill.total,skill.manual+skill.pinned+skill.auto);
});
