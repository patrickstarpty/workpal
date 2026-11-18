import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {randomUUID} from 'node:crypto';

const scripts=['data','model'].map(name=>readFileSync(new URL('../src/'+name+'.js',import.meta.url),'utf8'));
function openWorkspace(previous){
  const values=new Map(previous?[['workpal.studio.v2',JSON.stringify(previous)]]:[]);
  const localStorage={get length(){return values.size;},key:i=>[...values.keys()][i],getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value)};
  const ctx=vm.createContext({localStorage,crypto:{randomUUID}});
  for(const script of scripts)vm.runInContext(script,ctx);
  return ctx.WorkpalStudio;
}

function deliveryPayload(checks) {
  return {artifacts:[{title:'Review fixture',body:'Manually entered example change and verification notes.'}],
    evidence:checks.map(criterion=>({criterion,evidence:'Reviewer-provided record for '+criterion})),limitations:'Offline example; no code was executed.'};
}
function approve(studio,run,note='Accepted the supplied evidence.') {
  return studio.decide(run.id,run.stage,'approve',note,{acknowledged:true});
}

test('an open run is reused and a closed review cannot be approved twice',()=>{
  const studio=openWorkspace();
  const {db,start,changeRun}=studio;
  const issue=db.tasks.find(t=>t.id==='TAP-030');
  const run=start(issue,'brainstorming');
  assert.equal(start(issue,'brainstorming').id,run.id);
  assert.throws(()=>changeRun(run,'deliver','  '));
  changeRun(run,'deliver','Ready for acceptance',deliveryPayload(issue.checks));
  assert.equal(issue.status,'review');
  approve(studio,run);
  assert.equal(issue.status,'done');
  assert.throws(()=>approve(studio,run));
});

test('a mention can complete while the assigned agent keeps its open run',()=>{
  const {db,start,comment,changeRun,openRun}=openWorkspace();
  const issue=db.tasks.find(t=>t.id==='TAP-030');
  const owner=issue.owner;
  const main=start(issue,'brainstorming');
  comment(issue,'@Quality partner please check the acceptance criteria');
  const reply=db.runs.find(r=>r.kind==='reply');
  assert.equal(openRun(issue.id).id,main.id);
  assert.equal(reply.status,'queued');
  changeRun(reply,'claim');
  changeRun(reply,'deliver','Review the missing source case');
  assert.equal(issue.owner,owner);
  assert.equal(issue.status,'active');
  assert.equal(main.status,'running');
  assert.match(issue.activity[0].text,/missing source/);
});

test('existing workspaces retain authored edits during status and directory migration',()=>{
  const previous=JSON.parse(JSON.stringify(openWorkspace().db));
  delete previous.issueSchema;
  const issue={...previous.tasks[0],id:'WP-014',project:'Workpal'};
  previous.tasks.push(issue);previous.projects.push('Workpal');
  delete previous.tapProjectMigration;
  Object.assign(issue,{title:'Prepare November release',owner:'Researcher',status:'todo',checks:['Keep my criteria']});
  const {db}=openWorkspace(previous);
  const result=db.tasks.find(t=>t.id===issue.id);
  assert.equal(result.title,'Prepare November release');
  assert.equal(result.owner,'Patrick');
  assert.equal(result.status,'backlog');
  assert.equal(result.checks[0],'Keep my criteria');
  assert.equal(db.skills.filter(s=>s.id==='impeccable').length,1);
});

test('workspaces start with the public directory and keep independent records',()=>{
  const studio=openWorkspace();
  assert.deepEqual([...studio.db.projects],['TAP']);
  studio.db.skills.push({id:'internal',name:'Internal TAP skill'});
  studio.db.notes.push({text:'Only in TAP'});
  studio.save();
  const other=studio.createWorkspace('Atlas');
  assert.throws(()=>studio.createWorkspace(' atlas '),/already exists/);
  assert.ok(studio.selectWorkspace(other));
  for(const key of ['projects','tasks','runs','deliveries','messages','agents','panels','notes','reports','bookmarks'])assert.equal(studio.db[key].length,0);
  assert.ok(studio.db.skills.some(s=>s.id==='impeccable'));
  assert.ok(!studio.db.skills.some(s=>s.id==='internal'));
  studio.db.projects.push('Atlas Core');
  studio.save();
  assert.ok(studio.selectWorkspace('tap'));
  assert.equal(studio.db.notes[0].text,'Only in TAP');
  assert.deepEqual([...studio.db.projects],['TAP']);
  assert.ok(studio.selectWorkspace(other));
  assert.deepEqual([...studio.db.projects],['Atlas Core']);
});

test('delivery completes its run and applies a reusable workflow handoff on the same issue',()=>{
  const studio=openWorkspace();
  const {db,start,changeRun,workflowFor}=studio;
  db.workflows.push({id:'FLOW-001',name:'Delivery',steps:[
    {status:'active',owner:'Engineering partner',instructions:'Implement acceptance criteria.',next:'review',rejected:''},
    {status:'review',owner:'Quality partner',instructions:'Check the acceptance evidence.',next:'done',rejected:'active'}
  ]});
  db.projectSettings.find(p=>p.project==='TAP').workflowId='FLOW-001';
  const issue=db.tasks.find(t=>t.id==='TAP-030');
  issue.owner='Engineering partner';
  const description=issue.description;
  const run=start(issue,'frontend-design');
  changeRun(run,'deliver','Implementation ready.');
  assert.equal(run.status,'finished');
  assert.equal(issue.status,'review');
  assert.equal(issue.owner,'Quality partner');
  assert.equal(issue.description,description);
  assert.equal(workflowFor('TAP').name,'Delivery');
  const review=studio.openRun(issue.id,'Quality partner');
  assert.equal(review.status,'queued');
  assert.equal(review.instructions,'Check the acceptance evidence.');
  assert.equal(review.origin,'Workflow · Delivery');
  assert.ok(issue.activity.some(e=>e.text.includes('Implementation ready.')));
  studio.decide(run.id,run.stage,'return','Cover missing-source citations.');
  assert.equal(issue.status,'active');
  assert.equal(issue.owner,'Engineering partner');
  assert.equal(run.status,'finished');
  assert.equal(run.reviewDecision,'return');
  assert.equal(review.status,'cancelled');
  assert.equal(studio.openRun(issue.id,'Engineering partner').status,'queued');
});

test('finishing a run leaves issue status intact and distinct agents may run on one issue',()=>{
  const {db,start,changeRun,openRun}=openWorkspace();
  const issue=db.tasks.find(t=>t.id==='TAP-030');
  const first=start(issue,'brainstorming');
  const second=start(issue,'webapp-testing','Quality partner',true);
  assert.notEqual(first.id,second.id);
  assert.equal(openRun(issue.id,'Quality partner').id,second.id);
  changeRun(first,'finish');
  assert.equal(issue.status,'active');
  assert.equal(first.status,'finished');
  assert.equal(second.status,'queued');
});

test('project-lead handoffs assign a human and workflow changes can preserve ownership',()=>{
  const {db,start,transitionIssue}=openWorkspace();
  const issue=db.tasks.find(t=>t.id==='TAP-030');
  const config=db.projectSettings.find(p=>p.project==='TAP');
  db.workflows.push({id:'FLOW-LEAD',name:'Sign-off',steps:[{status:'review',owner:'Project lead',instructions:'Approve the release.',next:'done',rejected:'active'}]});
  config.workflowId='FLOW-LEAD';config.lead='Patrick';
  const run=start(issue,'brainstorming');
  transitionIssue(issue,'review',{handoff:false});
  assert.equal(issue.owner,'Product partner');
  assert.equal(run.status,'running');
  transitionIssue(issue,'active',{handoff:false});
  transitionIssue(issue,'review');
  assert.equal(issue.owner,'Patrick');
  assert.equal(run.status,'cancelled');
  assert.equal(db.runs.filter(r=>r.task===issue.id&&r.status==='queued').length,0);
});

test('legacy review runs and project reviewer settings migrate without losing history',()=>{
  const previous=JSON.parse(JSON.stringify(openWorkspace().db));
  const config=previous.projectSettings.find(p=>p.project==='TAP');
  config.reviewer='Quality partner';delete config.workflowId;
  const run=previous.runs.find(r=>r.id==='RUN-014');
  run.status='waiting';delete run.delivered;
  const events=JSON.stringify(run.events);
  const studio=openWorkspace(previous);
  const migrated=studio.db.runs.find(r=>r.id===run.id);
  assert.equal(migrated.status,'finished');
  assert.equal(migrated.delivered,true);
  assert.equal(JSON.stringify(migrated.events),events);
  assert.equal(studio.workflowFor('TAP').steps.find(s=>s.status==='review').owner,'Quality partner');
  const again=openWorkspace(JSON.parse(JSON.stringify(studio.db)));
  assert.equal(again.db.workflows.length,studio.db.workflows.length);
});

test('chat execution reports support runs without issues',()=>{
  const {db,report}=openWorkspace();
  db.runs.push({id:'RUN-CHAT',kind:'chat',conversation:'chat-1',task:null,agent:'Product partner',title:'Review rollout options',status:'queued',stage:0,artifacts:[],events:[]});
  const output=report('execution','','RUN-CHAT');
  assert.match(output.body,/Review rollout options/);
  assert.match(output.body,/State: queued/);
  assert.match(output.body,/Product partner/);
});

test('comment routing respects explicit squad mentions and human mentions',()=>{
  const {db,start,comment,changeRun}=openWorkspace();
  const issue=db.tasks.find(t=>t.id==='TAP-030');
  const main=start(issue,'brainstorming');
  const before=db.runs.length;
  comment(issue,'@Patrick please review this.');
  comment(issue,'@all please check the release brief.');
  assert.equal(db.runs.length,before);
  assert.equal(main.events.filter(e=>e.type==='comment.received').length,0);
  comment(issue,'@TAP delivery coordinate the next step.');
  const guest=db.runs.find(r=>r.task===issue.id&&r.agent==='Engineering partner');
  assert.equal(guest.status,'queued');
  assert.equal(issue.owner,'Product partner');
  comment(issue,'@Engineering partner include the citation case.');
  assert.equal(db.runs.filter(r=>r.task===issue.id&&r.agent==='Engineering partner').length,1);
  assert.ok(guest.events.some(e=>e.text.includes('citation case')));
  changeRun(guest,'claim');
  changeRun(guest,'cancel');
  assert.equal(issue.status,'active');
  assert.equal(main.status,'running');
});

test('replying reopens a resolved thread, subscribes the author, and queues only the mentioned agent',()=>{
  const {db,comment}=openWorkspace();
  const issue=db.tasks.find(t=>t.id==='TAP-030');
  comment(issue,'@Patrick please confirm scope.');
  const thread=issue.activity.find(e=>e.kind==='comment');
  thread.resolved=true;issue.subscribed=false;
  const before=db.runs.length,owner=issue.owner,status=issue.status;
  comment(issue,'@Quality partner verify the updated criteria.',{replyTo:thread.id});
  assert.equal(thread.resolved,false);
  assert.equal(thread.replies.length,1);
  assert.equal(issue.subscribed,true);
  assert.equal(db.runs.length,before+1);
  assert.equal(db.runs[0].agent,'Quality partner');
  assert.equal(db.runs[0].status,'queued');
  assert.equal(issue.owner,owner);
  assert.equal(issue.status,status);
});

test('only the latest delivery may be approved after two submissions',()=>{
  const studio=openWorkspace();
  const issue=studio.db.tasks.find(t=>t.id==='TAP-030');
  const first=studio.start(issue,'brainstorming');
  studio.changeRun(first,'deliver','First submission',deliveryPayload(issue.checks));
  const older=studio.latestDelivery(issue.id);
  const second=studio.start(issue,'webapp-testing');
  studio.changeRun(second,'deliver','Second submission',deliveryPayload(issue.checks));
  const latest=studio.latestDelivery(issue.id);
  assert.notEqual(latest.id,older.id);
  assert.throws(()=>approve(studio,first));
  assert.equal(first.reviewDecision,undefined);
  assert.equal(issue.status,'review');
  approve(studio,second);
  assert.equal(issue.status,'done');
  assert.equal(second.reviewDecision,'approve');
});

test('a summary alone and partial criterion evidence cannot authorize approval',()=>{
  const studio=openWorkspace();
  const issue=studio.db.tasks.find(t=>t.id==='TAP-030');
  issue.checks=['Keep upload progress','Allow retry after reconnect'];
  const noEvidence=studio.start(issue,'webapp-testing');
  studio.changeRun(noEvidence,'deliver','Ready to inspect');
  assert.throws(()=>approve(studio,noEvidence));
  assert.equal(issue.status,'review');
  studio.decide(noEvidence.id,noEvidence.stage,'return','Provide acceptance evidence.');
  const partial=studio.start(issue,'webapp-testing');
  const payload=deliveryPayload(issue.checks);
  payload.evidence.pop();
  studio.changeRun(partial,'deliver','One criterion covered',payload);
  assert.throws(()=>approve(studio,partial));
  assert.equal(issue.status,'review');
  assert.equal(partial.reviewDecision,undefined);
});

test('approval requires both a concrete artifact and explicit reviewer acknowledgement',()=>{
  const studio=openWorkspace();
  const issue=studio.db.tasks.find(t=>t.id==='TAP-030');
  const missingArtifact=studio.start(issue,'webapp-testing');
  const payload=deliveryPayload(issue.checks);
  payload.artifacts=[];
  studio.changeRun(missingArtifact,'deliver','Evidence without an artifact',payload);
  assert.throws(()=>approve(studio,missingArtifact));
  studio.decide(missingArtifact.id,missingArtifact.stage,'return','Attach the proposed change.');
  const complete=studio.start(issue,'webapp-testing');
  studio.changeRun(complete,'deliver','All evidence supplied',deliveryPayload(issue.checks));
  assert.throws(()=>studio.decide(complete.id,complete.stage,'approve'));
  assert.equal(complete.reviewDecision,undefined);
  approve(studio,complete);
  assert.equal(issue.status,'done');
});

test('review approval follows the configured destination instead of always completing the issue',()=>{
  const studio=openWorkspace();
  const {db}=studio;
  db.workflows.push({id:'FLOW-RELEASE',name:'Release handoff',steps:[
    {status:'active',owner:'',instructions:'Prepare change.',next:'review',rejected:''},
    {status:'review',owner:'Patrick',instructions:'Inspect evidence.',next:'todo',rejected:'blocked'}
  ]});
  db.projectSettings.find(p=>p.project==='TAP').workflowId='FLOW-RELEASE';
  const issue=db.tasks.find(t=>t.id==='TAP-030');
  const run=studio.start(issue,'webapp-testing');
  studio.changeRun(run,'deliver','Ready for release planning',deliveryPayload(issue.checks));
  approve(studio,run);
  assert.equal(issue.status,'todo');
  assert.equal(run.status,'finished');
  assert.equal(run.reviewDecision,'approve');
});

test('starting formal work cannot reuse a queued reply or lose the selected skill',()=>{
  const studio=openWorkspace();
  const issue=studio.db.tasks.find(t=>t.id==='TAP-030');
  studio.comment(issue,'Please check the requirement wording.');
  const reply=studio.db.runs.find(r=>r.task===issue.id&&r.kind==='reply');
  assert.ok(reply);
  const run=studio.start(issue,'webapp-testing');
  assert.notEqual(run.id,reply.id);
  assert.equal(run.kind,'execution');
  assert.equal(run.skill,'webapp-testing');
  assert.equal(run.status,'running');
  assert.equal(reply.status,'queued');
  assert.equal(studio.openRun(issue.id,issue.owner).id,run.id);
  studio.changeRun(reply,'claim');
  studio.changeRun(reply,'deliver','A discussion response');
  assert.equal(studio.latestDelivery(issue.id),undefined);
  assert.equal(issue.status,'active');
});

test('historical execution reports retain launch requirements after edits and reload',()=>{
  const studio=openWorkspace();
  const issue=studio.db.tasks.find(t=>t.id==='TAP-030');
  issue.title='Original upload recovery';
  issue.description='Original reconnect requirement';
  issue.checks=['Original acceptance criterion'];
  const profile=studio.db.agents.find(a=>a.name===issue.owner);
  profile.instructions='Original agent instructions';
  const skill=studio.db.skills.find(s=>s.id==='webapp-testing');
  skill.description='Original skill method';
  skill.version='1.0';
  const run=studio.start(issue,skill.id);
  studio.changeRun(run,'deliver','Captured requirement',deliveryPayload(issue.checks));
  issue.title='Changed task title';
  issue.description='Changed goal after launch';
  issue.checks=['Changed acceptance after launch'];
  profile.instructions='Changed agent instructions';
  skill.description='Changed skill method';skill.version='2.0';
  const reopened=openWorkspace(JSON.parse(JSON.stringify(studio.db)));
  const snapshot=reopened.latestDelivery(issue.id).inputSnapshot;
  assert.equal(snapshot.task.description,'Original reconnect requirement');
  assert.equal(snapshot.skill.description,'Original skill method');
  assert.equal(snapshot.skill.version,'1.0');
  assert.deepEqual([...snapshot.task.checks],['Original acceptance criterion']);
  const body=reopened.report('execution','',run.id).body;
  assert.match(body,/Original upload recovery/);
  assert.match(body,/Original acceptance criterion/);
  assert.doesNotMatch(body,/Changed task title|Changed acceptance after launch/);
  assert.throws(()=>approve(reopened,reopened.db.runs.find(r=>r.id===run.id)));
});

test('cancelling a new attempt preserves review of the selected delivery',()=>{
  const studio=openWorkspace();
  const issue=studio.db.tasks.find(t=>t.id==='TAP-030');
  const first=studio.start(issue,'brainstorming');
  studio.changeRun(first,'deliver','Prior delivery',deliveryPayload(issue.checks));
  const newer=studio.start(issue,'webapp-testing',issue.owner,true);
  assert.equal(issue.status,'review');
  assert.equal(studio.reviewEligibility(studio.currentDelivery(issue.id)),'');
  studio.changeRun(newer,'cancel');
  approve(studio,first);
  assert.equal(first.reviewDecision,'approve');
});

test('requirement edits invalidate approval without changing the recorded delivery',()=>{
  for(const edit of [issue=>issue.checks.push('New criterion'),issue=>{issue.description='Changed scope';}]){
    const studio=openWorkspace();
    const issue=studio.db.tasks.find(t=>t.id==='TAP-030');
    const run=studio.start(issue,'webapp-testing');
    studio.changeRun(run,'deliver','Original delivery',deliveryPayload(issue.checks));
    const before=JSON.stringify(studio.latestDelivery(issue.id));
    edit(issue);
    assert.throws(()=>approve(studio,run));
    assert.equal(issue.status,'review');
    assert.equal(JSON.stringify(studio.latestDelivery(issue.id)),before);
  }
});

test('return and resubmit preserves version history, source runs and both decisions',()=>{
  const studio=openWorkspace();
  const issue=studio.db.tasks.find(t=>t.id==='TAP-030');
  const first=studio.start(issue,'webapp-testing');
  studio.changeRun(first,'deliver','Version one',deliveryPayload(issue.checks));
  const v1=studio.latestDelivery(issue.id);
  assert.throws(()=>studio.decide(first.id,first.stage,'return','  '));
  studio.decide(first.id,first.stage,'return','Add reconnect evidence.');
  const second=studio.start(issue,'webapp-testing');
  studio.changeRun(second,'deliver','Version two',deliveryPayload(issue.checks));
  const v2=studio.latestDelivery(issue.id);
  assert.equal(second.inputSnapshot.previousDelivery.id,v1.id);
  assert.equal(second.inputSnapshot.previousDelivery.review.note,'Add reconnect evidence.');
  approve(studio,second,'The reconnect evidence is complete.');
  assert.equal(v1.version,1);
  assert.equal(v2.version,2);
  assert.equal(v1.run,first.id);
  assert.equal(v2.run,second.id);
  assert.equal(v2.supersedes,v1.id);
  assert.equal(v1.review.decision,'return');
  assert.equal(v1.review.note,'Add reconnect evidence.');
  assert.equal(v2.review.decision,'approve');
  assert.equal(v2.review.reviewer,'Patrick');
  assert.equal(v2.review.destination,'done');
  assert.equal(first.reviewDecision,'return');
  assert.equal(second.reviewDecision,'approve');
  assert.ok(issue.activity.some(e=>e.text.includes('Add reconnect evidence.')));
  const reopened=openWorkspace(JSON.parse(JSON.stringify(studio.db)));
  assert.equal(reopened.db.deliveries.filter(d=>d.task===issue.id).length,2);
  assert.equal(reopened.latestDelivery(issue.id).id,v2.id);
  assert.equal(reopened.db.tasks.find(t=>t.id===issue.id).status,'done');
});

test('legacy delivered runs retain notes but cannot fabricate an execution input snapshot',()=>{
  const previous=JSON.parse(JSON.stringify(openWorkspace().db));
  previous.notes.push({text:'Keep local reviewer notes',page:'tasks'});
  const issue=previous.tasks.find(t=>t.id==='TAP-030');
  issue.status='review';issue.checks=['Current criterion is not historical evidence'];
  previous.runs.push({id:'RUN-LEGACY',task:issue.id,agent:issue.owner,stage:2,status:'finished',delivered:true,
    skill:'webapp-testing',events:[{type:'run.finished',text:'Original event',at:1}],
    artifacts:[{title:'Handoff note',body:'Original legacy handoff',stage:2,at:1}]});
  const studio=openWorkspace(previous);
  const run=studio.db.runs.find(r=>r.id==='RUN-LEGACY');
  assert.equal(studio.db.notes[0].text,'Keep local reviewer notes');
  assert.equal(run.artifacts[0].body,'Original legacy handoff');
  assert.equal(run.events[0].text,'Original event');
  assert.throws(()=>approve(studio,run));
  const body=studio.report('execution','',run.id).body;
  assert.match(body,/Original legacy handoff/);
  assert.doesNotMatch(body,/Current criterion is not historical evidence/);
  const reopened=openWorkspace(JSON.parse(JSON.stringify(studio.db)));
  assert.equal(reopened.db.deliveries.length,studio.db.deliveries.length);
});

test('a workflow review run can record a note without replacing the delivery or accepting it',()=>{
  const studio=openWorkspace();
  const {db}=studio;
  db.workflows.push({id:'FLOW-REVIEW-NOTE',name:'Review notes',steps:[
    {status:'review',owner:'Quality partner',instructions:'Inspect submitted artifacts.',next:'done',rejected:'active'}
  ]});
  db.projectSettings.find(p=>p.project==='TAP').workflowId='FLOW-REVIEW-NOTE';
  const issue=db.tasks.find(t=>t.id==='TAP-030');
  const execution=studio.start(issue,'webapp-testing');
  studio.changeRun(execution,'deliver','Delivery for review',deliveryPayload(issue.checks));
  const delivery=studio.latestDelivery(issue.id);
  const reviewer=studio.openRun(issue.id,'Quality partner','review');
  assert.equal(reviewer.kind,'review');
  studio.changeRun(reviewer,'claim');
  studio.changeRun(reviewer,'deliver','Review note recorded by a person.');
  assert.equal(studio.latestDelivery(issue.id).id,delivery.id);
  assert.equal(db.deliveries.filter(d=>d.task===issue.id).length,1);
  assert.equal(issue.status,'review');
  assert.equal(delivery.review,null);
  assert.throws(()=>approve(studio,reviewer));
  approve(studio,execution);
  assert.equal(issue.status,'done');
});

test('a delivery with no launch acceptance criteria cannot be approved',()=>{
  const studio=openWorkspace();
  const issue=studio.db.tasks.find(t=>t.id==='TAP-030');
  issue.checks=[];
  const run=studio.start(issue,'brainstorming');
  studio.changeRun(run,'deliver','A brief without acceptance criteria',deliveryPayload([]));
  assert.throws(()=>approve(studio,run));
  assert.equal(issue.status,'review');
  assert.equal(run.reviewDecision,undefined);
});

test('criterion status cannot be bypassed with text and not-applicable needs a rationale',()=>{
  for(const [status,evidence,allowed] of [
    ['missing','An evidence record is still needed.',false],
    ['supported','  ',false],
    ['unmet','The reconnect check failed.',false],
    ['not-applicable','  ',false],
    ['not-applicable','This task only changes the copy; reconnect behavior is outside its scope.',true]
  ]){
    const studio=openWorkspace();
    const issue=studio.db.tasks.find(t=>t.id==='TAP-030');
    issue.checks=['Check reconnect behavior'];
    const run=studio.start(issue,'webapp-testing');
    const payload=deliveryPayload(issue.checks);
    payload.evidence[0]={criterion:issue.checks[0],status,evidence};
    studio.changeRun(run,'deliver','Criterion status recorded',payload);
    if(!evidence.trim())assert.equal(studio.latestDelivery(issue.id).evidence[0].status,'missing');
    if(allowed){approve(studio,run);assert.equal(issue.status,'done');}
    else {assert.throws(()=>approve(studio,run));assert.equal(issue.status,'review');}
  }
});

test('an existing execution retains its delegated inputs and rejects a different skill or requirements',()=>{
  const {db,start}=openWorkspace();
  const issue=db.tasks.find(t=>t.id==='TAP-030');
  const run=start(issue,'brainstorming');
  assert.equal(start(issue,'brainstorming').id,run.id);
  assert.throws(()=>start(issue,'webapp-testing'),/existing run.*different inputs/i);
  assert.equal(run.skill,'brainstorming');
  issue.checks.push('A requirement added after delegation');
  assert.throws(()=>start(issue,'brainstorming'),/Cancel or finish/);
  assert.ok(!run.inputSnapshot.task.checks.includes('A requirement added after delegation'));
});
