import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {randomUUID} from 'node:crypto';
const scripts=['data','model'].map(name=>readFileSync(new URL('../src/'+name+'.js',import.meta.url),'utf8'));
function workspace(){
  const values=new Map();
  const localStorage={get length(){return values.size;},key:i=>[...values.keys()][i],getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value)};
  const ctx=vm.createContext({localStorage,crypto:{randomUUID}});
  for(const script of scripts)vm.runInContext(script,ctx);
  return ctx.WorkpalStudio;
}
function issue(studio){return studio.assignWork('Engineering partner',{title:'Recover upload',project:'TAP',checks:['Preserve progress'],status:'todo',queueRun:false}).task;}
function deliver(studio,run,title='Delivery'){
  return studio.changeRun(run,'deliver',title,{artifacts:[{title:'Review notes',body:'User supplied evidence.'}],evidence:run.inputSnapshot.task.checks.map(criterion=>({criterion,evidence:'Recorded evidence for '+criterion})),limitations:'Manually recorded.'});
}
function approve(studio,run){return studio.decide(run.id,run.stage,'approve','Accepted',{acknowledged:true});}
function workflow(studio){
  studio.db.workflows.push({id:'TEST',name:'Review',steps:[{status:'todo',owner:'Engineering partner',instructions:'Build',next:'review'},{status:'review',owner:'Quality partner',instructions:'Check the evidence',next:'done',rejected:'active'}]});
  studio.db.projectSettings.find(p=>p.project==='TAP').workflowId='TEST';
}

test('status editing routes once to a review run without ordinary assignment dispatch',()=>{
  const studio=workspace(),task=issue(studio);workflow(studio);
  const first=studio.start(task,'brainstorming');
  const before=studio.db.runs.length;
  const result=studio.updateIssue(task,{status:'review'},{queueRun:true});
  assert.equal(task.owner,'Quality partner');
  assert.equal(task.status,'review');
  assert.equal(studio.db.runs.length,before+1);
  assert.equal(result.run.kind,'review');
  assert.equal(result.run.status,'queued');
  assert.equal(first.status,'cancelled');
  studio.changeRun(result.run,'claim');
  assert.equal(task.status,'review');
});

test('do not start controls both ordinary assignment and workflow routing',()=>{
  const studio=workspace(),task=issue(studio);workflow(studio);
  task.status='backlog';
  const before=studio.db.runs.length;
  studio.updateIssue(task,{status:'todo'},{queueRun:false});
  assert.equal(task.status,'todo');
  assert.equal(task.owner,'Engineering partner');
  assert.equal(studio.db.runs.length,before);
  studio.updateIssue(task,{status:'review'},{queueRun:false});
  assert.equal(task.owner,'Quality partner');
  assert.equal(studio.db.runs.length,before);
});

test('reassignment cancels the old owner work without touching a parallel agent',()=>{
  const studio=workspace(),task=issue(studio);
  const owner=studio.start(task,'brainstorming');
  const parallel=studio.start(task,'webapp-testing','Quality partner');
  studio.updateIssue(task,{owner:'Patrick'},{queueRun:false});
  assert.equal(owner.status,'cancelled');
  assert.equal(parallel.status,'running');
  assert.equal(task.owner,'Patrick');
});

test('parallel submissions in either order retain one reviewable delivery and one selectable candidate',()=>{
  for(const reverse of [false,true]){
    const studio=workspace(),task=issue(studio);
    const a=studio.start(task,'brainstorming'),b=studio.start(task,'webapp-testing','Quality partner');
    const [first,last]=reverse?[b,a]:[a,b];
    deliver(studio,first,'First response');
    const initial=studio.currentDelivery(task.id);
    deliver(studio,last,'Later response');
    const candidate=studio.latestDelivery(task.id);
    assert.equal(studio.currentDelivery(task.id).id,initial.id);
    assert.equal(studio.reviewEligibility(initial),'');
    assert.equal(candidate.disposition,'candidate');
    assert.notEqual(candidate.id,initial.id);
    assert.throws(()=>approve(studio,last),/not the current/);
    studio.selectDelivery(candidate.id,'Use this more complete result.');
    assert.equal(studio.currentDelivery(task.id).id,candidate.id);
    assert.equal(initial.disposition,'candidate');
    approve(studio,last);
    assert.equal(task.status,'done');
    assert.equal(task.completion.kind,'delivery');
  }
});

test('a late result preserves manual completion and requires an explicit reason to reopen',()=>{
  const studio=workspace(),task=issue(studio);
  const run=studio.start(task,'brainstorming');
  assert.throws(()=>studio.updateIssue(task,{status:'done'},{queueRun:false}),/manually/);
  assert.equal(task.status,'active');
  studio.updateIssue(task,{status:'done'},{queueRun:false,manualReason:'Resolved without accepting agent output.'});
  assert.equal(task.completion.kind,'manual');
  const revision=task.operationRevision;
  deliver(studio,run);
  const candidate=studio.latestDelivery(task.id);
  assert.equal(task.status,'done');
  assert.equal(task.operationRevision,revision);
  assert.equal(candidate.disposition,'candidate');
  assert.equal(studio.currentDelivery(task.id),undefined);
  assert.throws(()=>studio.selectDelivery(candidate.id,''),/Explain/);
  studio.selectDelivery(candidate.id,'Reopen to inspect the late result.');
  assert.equal(task.status,'review');
  assert.equal(task.completion.kind,'manual');
  approve(studio,run);
  assert.equal(task.completion.kind,'delivery');
});

test('a later response cannot replace a delivery approved after its run began',()=>{
  const studio=workspace(),task=issue(studio);
  const first=studio.start(task,'brainstorming');deliver(studio,first);
  const selected=studio.currentDelivery(task.id);
  const second=studio.start(task,'webapp-testing','Quality partner');
  assert.equal(task.status,'review');
  approve(studio,first);
  deliver(studio,second,'Late revision');
  assert.equal(task.status,'done');
  assert.equal(studio.currentDelivery(task.id).id,selected.id);
  assert.equal(studio.latestDelivery(task.id).disposition,'candidate');
  assert.equal(selected.review.decision,'approve');
});

test('cancelling a queued retry leaves the previous delivery immediately reviewable',()=>{
  const studio=workspace(),task=issue(studio);
  const run=studio.start(task,'brainstorming');deliver(studio,run);
  const current=studio.currentDelivery(task.id);
  const retry=studio.start(task,'webapp-testing',task.owner,true);
  studio.changeRun(retry,'cancel');
  assert.equal(studio.currentDelivery(task.id).id,current.id);
  assert.equal(studio.reviewEligibility(current),'');
  approve(studio,run);
  assert.equal(task.status,'done');
});

test('sequential rework replaces its source delivery while retaining the old decision',()=>{
  const studio=workspace(),task=issue(studio);
  const first=studio.start(task,'brainstorming');deliver(studio,first);
  const previous=studio.currentDelivery(task.id);
  studio.decide(first.id,first.stage,'return','Add the timeout case.');
  const second=studio.start(task,'webapp-testing');deliver(studio,second,'Revised');
  const revised=studio.currentDelivery(task.id);
  assert.equal(revised.supersedes,previous.id);
  assert.equal(previous.disposition,'history');
  assert.equal(previous.review.note,'Add the timeout case.');
  approve(studio,second);
});

test('a human change to issue status keeps the old execution result as a candidate',()=>{
  const studio=workspace(),task=issue(studio);
  const run=studio.start(task,'brainstorming');
  studio.updateIssue(task,{status:'blocked'},{queueRun:false});
  deliver(studio,run);
  assert.equal(task.status,'blocked');
  assert.equal(studio.latestDelivery(task.id).disposition,'candidate');
  assert.equal(studio.currentDelivery(task.id),undefined);
});

test('Autopilot captures a usable summary contract before queuing and supports template criteria',()=>{
  for(const custom of [false,true]){
    const studio=workspace();
    const auto=studio.db.autopilots[0];
    if(custom)auto.checks=['Cite the source issue for each blocker'];
    const event=studio.triggerAutopilot(auto.id);
    const task=studio.db.tasks.find(t=>t.id===event.task),run=studio.db.runs.find(r=>r.id===event.run);
    assert.equal(task.workKind,'summary');
    assert.equal(run.inputSnapshot.task.checks.length,1);
    assert.equal(run.inputSnapshot.task.checks[0],custom?auto.checks[0]:'Provide the requested summary with sources and open questions.');
    studio.changeRun(run,'claim');deliver(studio,run,'Requested summary');approve(studio,run);
    assert.equal(task.status,'done');
  }
});


test('cancelling an old run does not overwrite a newer human issue update',()=>{
  const studio=workspace(),task=issue(studio);
  const run=studio.start(task,'brainstorming');
  studio.updateIssue(task,{description:'New context with a deliberate active status',status:'active'},{queueRun:false});
  studio.changeRun(run,'cancel');
  assert.equal(task.status,'active');
});
