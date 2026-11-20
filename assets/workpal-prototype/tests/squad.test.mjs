import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {randomUUID} from 'node:crypto';

const scripts=['data','model'].map(name=>readFileSync(new URL('../src/'+name+'.js',import.meta.url),'utf8'));
function workspace(previous){
  const values=new Map(previous?[['workpal.studio.v2',JSON.stringify(previous)]]:[]);
  const localStorage={get length(){return values.size;},key:i=>[...values.keys()][i],getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value)};
  const ctx=vm.createContext({localStorage,crypto:{randomUUID}});
  for(const script of scripts)vm.runInContext(script,ctx);
  return ctx.WorkpalStudio;
}
const assignment={title:'Recover upload progress',description:'Keep the selected upload after reconnect.',checks:['Keep the file','Retain the offset'],project:'TAP',status:'todo',priority:'High',queueRun:true};

test('squad assignment keeps squad ownership and queues only its leader despite project routing',()=>{
  const studio=workspace(),{db}=studio;
  const squad=db.squads[0],before=db.runs.length;
  db.workflows.push({id:'ASSIGN-FLOW',name:'Route elsewhere',steps:[{status:'todo',owner:'Quality partner',instructions:'Review first',next:'review'}]});
  db.projectSettings.find(p=>p.project==='TAP').workflowId='ASSIGN-FLOW';
  const {task,run}=studio.assignWork(squad.name,assignment);
  assert.equal(task.owner,squad.name);
  assert.equal(task.status,'todo');
  assert.equal(task.priority,'High');
  assert.equal(db.runs.length,before+1);
  assert.equal(run.agent,squad.leader);
  assert.equal(run.kind,'execution');
  assert.equal(run.status,'queued');
  assert.equal(run.task,task.id);
  assert.equal(run.origin,'Squad · '+squad.name);
  assert.equal(db.runs.filter(r=>r.task===task.id).length,1);
  assert.ok(task.activity.some(entry=>entry.text.includes('assigned to '+squad.name)));
});

test('backlog and unchecked queue option retain assignment without dispatching work',()=>{
  for(const values of [{status:'backlog',queueRun:true},{status:'todo',queueRun:false}]){
    const studio=workspace(),{db}=studio;
    const before=db.runs.length;
    const {task,run}=studio.assignWork(db.squads[0].name,{...assignment,...values});
    assert.equal(task.owner,db.squads[0].name);
    assert.equal(task.status,values.status);
    assert.equal(run,null);
    assert.equal(db.runs.length,before);
  }
});

test('squad run snapshots roles and instructions independently of later configuration edits',()=>{
  const studio=workspace(),{db}=studio;
  const squad=db.squads[0];
  const leader=db.agents.find(a=>a.name===squad.leader);
  leader.instructions='Keep existing implementation constraints.';
  squad.roles=[{name:leader.name,role:'Coordinate the change'},{name:'Quality partner',role:'Check evidence'}];
  const {task,run}=studio.assignWork(squad.name,assignment);
  const captured=JSON.stringify(run.inputSnapshot.context.squad);
  assert.equal(run.context.instructions,leader.instructions);
  assert.equal(run.context.squad.instructions,squad.instructions);
  assert.equal(run.inputSnapshot.context.squad.roles[1].role,'Check evidence');
  squad.roles[1].role='Changed role';squad.members.pop();squad.instructions='New instructions';squad.leader='Quality partner';
  assert.equal(JSON.stringify(run.context.squad),captured);
  assert.equal(JSON.stringify(run.inputSnapshot.context.squad),captured);
  run.context.squad.instructions='Edited current run metadata';
  assert.equal(JSON.stringify(run.inputSnapshot.context.squad),captured);
  const reopened=workspace(JSON.parse(JSON.stringify(db)));
  assert.equal(JSON.stringify(reopened.db.runs.find(r=>r.id===run.id).inputSnapshot.context.squad),captured);
  assert.equal(reopened.db.tasks.find(t=>t.id===task.id).owner,squad.name);
});

test('invalid squad leader prevents queued assignment before any records are created',()=>{
  for(const broken of ['missing-agent','not-a-member']){
    const studio=workspace(),{db}=studio;
    const squad=db.squads[0];
    if(broken==='missing-agent')squad.leader='No longer available';
    else squad.members=squad.members.filter(name=>name!==squad.leader);
    const tasks=db.tasks.length,runs=db.runs.length;
    assert.throws(()=>studio.assignWork(squad.name,assignment),/squad leader/);
    assert.equal(db.tasks.length,tasks);
    assert.equal(db.runs.length,runs);
    const {task,run}=studio.assignWork(squad.name,{...assignment,queueRun:false});
    assert.equal(task.owner,squad.name);
    assert.equal(run,null);
  }
});

test('assignment rejects invalid inputs atomically and retains user content as text',()=>{
  const studio=workspace(),{db}=studio;
  const squad=db.squads[0];
  const before=db.tasks.length;
  for(const values of [{title:'  '},{title:'a'.repeat(181)},{project:'Unknown project'},{status:'done'},{checks:[42]}]){
    assert.throws(()=>studio.assignWork(squad.name,{...assignment,...values}));
    assert.equal(db.tasks.length,before);
  }
  assert.throws(()=>studio.assignWork('Unknown target',assignment));
  assert.equal(db.tasks.length,before);
  const text='<img src=x onerror="alert(1)">';
  const {task,run}=studio.assignWork(squad.name,{...assignment,title:'  '+text+'  ',description:text,checks:[text],queueRun:false});
  assert.equal(task.title,text);
  assert.equal(task.description,text);
  assert.equal(task.checks[0],text);
  assert.equal(run,null);
});

test('agent Assign work uses the same create-only contract without inventing a squad',()=>{
  const studio=workspace(),{db}=studio;
  const agent=db.agents.find(a=>a.name==='Quality partner');
  const {task,run}=studio.assignWork(agent.name,{...assignment,project:''});
  assert.equal(task.owner,agent.name);
  assert.equal(run.agent,agent.name);
  assert.equal(task.project,'');
  assert.equal(run.context.squad,undefined);
  assert.equal(run.inputSnapshot.context.squad,undefined);
  assert.match(task.id,/^ISS-/);
});
