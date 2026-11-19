import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

const source=readFileSync(new URL('../src/analytics-data.js',import.meta.url),'utf8');
function analytics(){const context=vm.createContext({});vm.runInContext(source,context);return context.WorkpalAnalyticsData;}
const now=new Date(2026,10,18,15,30).getTime();
const when=(day,hour=12,minute=0)=>new Date(2026,10,day,hour,minute).getTime();
function record(id,at,changes={}){
  return {id,at,agent:'Engineering partner',team:'engineering',project:'TAP',input:100,output:20,cacheRead:30,cacheWrite:5,cost:0.25,seconds:75,status:'completed',...changes};
}
const close=(actual,expected)=>assert.ok(Math.abs(actual-expected)<0.000001,`${actual} != ${expected}`);

test('TAP gets dated fixture history once without modifying operational records or other workspaces',()=>{
  const api=analytics(),tap={tasks:[{id:'TAP-1'}],runs:[{id:'RUN-1'}]},other={};
  const before=JSON.stringify(tap);
  assert.equal(api.ensure(tap,'tap',now),true);
  assert.equal(tap.analyticsHistory.source,'fixture');
  assert.ok(tap.analyticsHistory.records.length>400);
  assert.ok(tap.analyticsHistory.records.every(row=>row.at<=now));
  assert.equal(new Set(tap.analyticsHistory.records.filter(row=>row.status==='failed').map(row=>row.failureClass)).size,7);
  const saved=JSON.stringify(tap.analyticsHistory);
  assert.equal(api.ensure(tap,'tap',when(25)),false);
  assert.equal(JSON.stringify(tap.analyticsHistory),saved);
  assert.equal(JSON.stringify({tasks:tap.tasks,runs:tap.runs}),before);
  assert.equal(api.ensure(other,'symphony',now),true);
  assert.equal(other.analyticsHistory.records.length,0);
  assert.equal(api.snapshot(other,{now}).totals.runs,0);
  other.analyticsHistory.records.push(record('custom',now));
  assert.equal(api.ensure(other,'symphony',when(25)),false);
  assert.equal(other.analyticsHistory.records.length,1);
  assert.equal(tap.analyticsHistory.records.some(row=>row.id==='custom'),false);
});

test('one-day range starts at local midnight, includes today and excludes future records',()=>{
  const api=analytics(),db={analyticsHistory:{records:[
    record('yesterday',when(17,23,59)),record('midnight',when(18,0)),
    record('now',now),record('future',now+1),record('bad-date','not-a-date'),
  ]}};
  const result=api.snapshot(db,{days:1,now});
  assert.deepEqual(Array.from(result.records,row=>row.id),['midnight','now']);
  assert.equal(result.totals.runs,2);
  assert.equal(result.daily.length,1);
  assert.equal(result.daily[0].key,'2026-11-18');
  assert.equal(result.daily[0].tokens,310);
});

test('project and team filters apply together and exclude unattached chat usage from a project',()=>{
  const api=analytics(),db={analyticsHistory:{records:[
    record('engineering',now),record('quality',now,{agent:'Quality partner',team:'quality'}),
    record('chat',now,{project:''}),record('another-project',now,{project:'Next'}),
  ]}};
  assert.equal(api.snapshot(db,{now}).totals.runs,4);
  assert.equal(api.snapshot(db,{project:'TAP',now}).totals.runs,2);
  const result=api.snapshot(db,{project:'TAP',team:'engineering',now});
  assert.deepEqual(Array.from(result.records,row=>row.id),['engineering']);
  assert.equal(result.agents.length,1);
  assert.equal(result.totals.cost,0.25);
  assert.equal(api.snapshot(db,{project:'Missing',now}).totals.runs,0);
});

test('daily buckets, Monday weeks, agents and failure details reconcile to the same scoped totals',()=>{
  const api=analytics(),db={analyticsHistory:{asOf:now,records:[
    record('excluded',when(11)),record('thursday',when(12)),record('sunday',when(15),{status:'failed',failureClass:'auth',reason:'credentials'}),
    record('monday',when(16),{agent:'Quality partner',team:'quality',status:'failed',failureClass:'timeout',reason:'run_timeout'}),
    record('wednesday',when(18),{agent:'Quality partner',team:'quality'}),
  ]}};
  const result=api.snapshot(db,{days:7,now});
  assert.equal(result.totals.runs,4);
  assert.equal(result.totals.failed,2);
  assert.equal(result.totals.affected,2);
  assert.equal(result.daily.length,7);
  assert.deepEqual(Array.from(result.weekly,row=>row.key),['2026-11-09','2026-11-16']);
  assert.deepEqual(Array.from(result.weekly,row=>row.runs),[2,2]);
  assert.deepEqual(Array.from(result.weekly,row=>row.partial),[false,true]);
  assert.equal(result.weekly[1].days,3);
  for(const key of ['tokens','cost','seconds','runs','failed']){
    for(const rows of [result.daily,result.weekly,result.agents])close(rows.reduce((sum,row)=>sum+row[key],0),result.totals[key]);
  }
  assert.equal(result.classes.reduce((sum,row)=>sum+row.count,0),result.totals.failed);
  assert.equal(result.reasons.reduce((sum,row)=>sum+row.count,0),result.totals.failed);
  assert.ok(result.agents.every(agent=>agent.failureRate===50));
  assert.equal(result.asOf,now);
});

test('empty or malformed imports remain safe and failures with unknown classifications stay visible',()=>{
  const api=analytics(),db={analyticsHistory:{source:'import',records:[
    record('unknown',now,{status:'failed',failureClass:'new-provider-code',reason:'new_error',input:-10,output:'25',cacheRead:NaN,cost:Infinity}),
    record('queued',now,{status:'queued'}),
  ]}};
  const result=api.snapshot(db,{now});
  assert.equal(result.totals.runs,1);
  assert.equal(result.totals.tokens,30);
  assert.equal(result.totals.cost,0);
  assert.equal(result.classes[0].key,'other');
  assert.equal(result.reasons[0].key,'new_error');
  assert.equal(db.analyticsHistory.records[0].failureClass,'new-provider-code');
  const empty=api.snapshot({}, {days:7,now});
  assert.equal(empty.daily.length,7);
  assert.equal(empty.totals.runs,0);
  assert.equal(empty.agents.length,0);
  assert.equal(empty.classes.length,0);
  const cleared={analyticsHistory:null};
  assert.equal(api.ensure(cleared,'tap',now),false);
  assert.equal(api.snapshot(cleared,{now}).totals.runs,0);
});

test('format helpers display compact counts, currency, durations and explicit failure rates',()=>{
  const api=analytics();
  assert.equal(api.compact(1250000),'1.3M');
  assert.equal(api.money(4.256),'$4.26');
  assert.equal(api.duration(0),'0s');
  assert.equal(api.duration(75),'1m 15s');
  assert.equal(api.duration(3661),'1h 1m');
  assert.equal(api.rate(2,31),'6.5%');
  assert.equal(api.rate(0,0),'0%');
});

test('contribution links exact tickets, deduplicates commits, scopes dates and detects the Workpal trailer',()=>{
  const api=analytics();
  const commit={repository:'org/repo',sha:'one',message:'TAP-1 TAP-2 Fix\n\nCo-authored-by: Workpal <workpal@users.noreply.github.com>',at:when(18),additions:12,deletions:4};
  const db={tasks:[{id:'TAP-1',team:'engineering',project:'TAP'},{id:'TAP-2',team:'product',project:'TAP'}],contributionCommits:[commit,commit,{...commit,sha:'two',message:'TAP-1 Mention Workpal in prose'},{...commit,sha:'three',message:'TAP-10 Unknown'},{...commit,sha:'future',at:when(20)}]};
  const result=api.contribution(db,{days:1},now);
  assert.equal(result.totals.commits,2);assert.equal(result.totals.workpal,1);assert.equal(result.totals.human,1);assert.equal(result.totals.added,24);assert.equal(result.rows.length,2);assert.equal(result.excluded,1);
  assert.equal(api.contribution(db,{team:'product',days:1},now).totals.commits,1);
  assert.equal(api.contribution(db,{project:'Other',days:1},now).totals.commits,0);
  assert.throws(()=>api.parseCommits('[{"message":"bad"}]'));
  assert.equal(api.parseCommits(JSON.stringify([commit]))[0].sha,'one');
});

test('squad contribution uses explicit ancestry, deduplicates and separates ambiguous ownership',()=>{
  const api=analytics();
  const db={squads:[{name:'Alpha',leader:'Agent'},{name:'Beta',leader:'Agent'},{name:'Empty',leader:'Agent'}],tasks:[{id:'P-1',owner:'Alpha'},{id:'T-1',parent:'P-1',owner:'Agent'},{id:'T-2',owner:'Alpha'},{id:'T-3',owner:'Beta'},{id:'T-4',owner:'Agent'},{id:'T-5',parent:'T-6'},{id:'T-6',parent:'T-5'}]};
  const c=(sha,assisted=true)=>({repository:'repo',sha,assisted,additions:10,deletions:2});
  const result={rows:db.tasks.filter(t=>t.id.startsWith('T-')).map(t=>({...t,commits:t.id==='T-1'?[c('one'),c('shared')]:t.id==='T-2'?[c('one')]:t.id==='T-3'?[c('shared'),c('two',false)]:[c(t.id)]}))};
  const summary=api.squadContribution(db,result);
  assert.equal(summary.rows[0].commits,1);assert.equal(summary.rows[0].workpal,1);assert.equal(summary.rows[0].tickets,2);
  assert.equal(summary.rows[1].commits,1);assert.equal(summary.rows[1].human,1);assert.equal(summary.rows[2].commits,0);
  assert.equal(summary.shared,1);assert.equal(summary.unassigned,3);
  assert.equal(summary.rows.reduce((n,r)=>n+r.commits,0)+summary.shared+summary.unassigned,6);
});
