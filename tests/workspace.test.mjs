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

test('an open run is reused and a closed review cannot be approved twice',()=>{
  const {db,start,changeRun}=openWorkspace();
  const issue=db.tasks.find(t=>t.id==='TAP-030');
  const run=start(issue,'brainstorming');
  assert.equal(start(issue,'brainstorming').id,run.id);
  assert.throws(()=>changeRun(run,'deliver','  '));
  changeRun(run,'deliver','Ready for acceptance');
  assert.equal(issue.status,'review');
  changeRun(run,'approve');
  assert.equal(issue.status,'done');
  assert.throws(()=>changeRun(run,'approve'));
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
  for(const key of ['projects','tasks','runs','messages','agents','panels','notes','reports','bookmarks'])assert.equal(studio.db[key].length,0);
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
