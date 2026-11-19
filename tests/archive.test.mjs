import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {randomUUID} from 'node:crypto';

const scripts=['data','model'].map(name=>readFileSync(new URL('../src/'+name+'.js',import.meta.url),'utf8'));
function workspace(previous){
  const values=new Map(previous),writes=[];
  const localStorage={get length(){return values.size;},key:i=>[...values.keys()][i],getItem:key=>values.get(key)??null,setItem:(key,value)=>{values.set(key,value);writes.push(key);}};
  const ctx=vm.createContext({localStorage,crypto:{randomUUID}});
  for(const script of scripts)vm.runInContext(script,ctx);
  return {studio:ctx.WorkpalStudio,values,writes,localStorage};
}
function completed(studio,id='TAP-ARCHIVE'){
  const task={...JSON.parse(JSON.stringify(studio.db.tasks[0])),id,status:'done',activity:[{kind:'comment',id:'COMMENT-1',text:'Keep this review discussion.',replies:[{text:'Keep this reply.'}]}],completion:{kind:'manual',reason:'Accepted by owner.',at:12345}};
  studio.db.tasks.push(task);
  return task;
}

test('archiving and restoring preserve issue history, relationships, delivery records and local notes across reloads',()=>{
  const {studio,values}=workspace(),task=completed(studio),child=completed(studio,'TAP-CHILD');
  child.parent=task.id;child.status='active';
  task.parent=studio.db.tasks[0].id;
  studio.db.notes.push({text:'Advisor review notes must survive.'});
  studio.db.runs.push({id:'RUN-ARCHIVE',task:task.id,agent:task.owner,kind:'execution',status:'finished',events:[],artifacts:[]});
  studio.db.deliveries.push({id:'DEL-ARCHIVE',task:task.id,run:'RUN-ARCHIVE',version:1,summary:'Existing delivery',artifacts:[],evidence:[],review:{decision:'approve'},disposition:'current'});
  task.currentDeliveryId='DEL-ARCHIVE';
  const preserved=JSON.stringify({completion:task.completion,parent:task.parent,discussion:task.activity[0],notes:studio.db.notes,runs:studio.db.runs,deliveries:studio.db.deliveries});
  assert.equal(studio.archiveIssues([task.id,task.id]).length,1);
  assert.ok(task.archivedAt>0);
  assert.equal(task.status,'done');
  assert.equal(child.archivedAt,undefined);
  assert.equal(child.parent,task.id);
  assert.equal(preserved,JSON.stringify({completion:task.completion,parent:task.parent,discussion:task.activity[0],notes:studio.db.notes,runs:studio.db.runs,deliveries:studio.db.deliveries}));
  const reopened=workspace(values).studio,restored=reopened.db.tasks.find(item=>item.id===task.id);
  assert.equal(restored.archivedAt,task.archivedAt);
  assert.equal(reopened.restoreIssues([task.id]).length,1);
  assert.equal(restored.archivedAt,undefined);
  assert.equal(restored.status,'done');
  assert.equal(restored.currentDeliveryId,'DEL-ARCHIVE');
  assert.equal(restored.activity.length,1);
  assert.equal(restored.activity[0].text,'Keep this review discussion.');
  assert.equal(restored.activity[0].replies[0].text,'Keep this reply.');
  assert.equal(reopened.db.notes.at(-1).text,'Advisor review notes must survive.');
});

test('invalid bulk selections cannot partly archive or restore issues',()=>{
  const {studio}=workspace(),first=completed(studio),second=completed(studio,'TAP-SECOND');
  second.status='active';
  let before=JSON.stringify(studio.db);
  for(const ids of [[first.id,second.id],[first.id,'MISSING'],[first.id,{}],'not-an-array']){
    assert.throws(()=>studio.archiveIssues(ids));
    assert.equal(JSON.stringify(studio.db),before);
  }
  studio.archiveIssues([first.id]);before=JSON.stringify(studio.db);
  assert.throws(()=>studio.restoreIssues([first.id,'MISSING']));
  assert.equal(JSON.stringify(studio.db),before);
  assert.equal(studio.archiveIssues([first.id]).length,0);
  assert.equal(studio.restoreIssues([second.id]).length,0);
  assert.equal(studio.archiveIssues([]).length,0);
});

test('archived issues require restore before edits, status moves, comments, runs or delivery selection',()=>{
  const {studio}=workspace(),task=completed(studio);
  studio.db.runs.push({id:'RUN-LATE',task:task.id,agent:task.owner,kind:'execution',status:'finished',delivered:true,events:[],artifacts:[]});
  studio.db.deliveries.push({id:'DEL-LATE',task:task.id,run:'RUN-LATE',version:1,summary:'Candidate',artifacts:[],evidence:[],review:null,disposition:'candidate'});
  studio.archiveIssues([task.id]);
  const before=JSON.stringify(studio.db);
  const changes=[
    ()=>studio.transitionIssue(task,'active'),
    ()=>studio.updateIssue(task,{title:'Do not partially update',status:'active'}),
    ()=>studio.comment(task,'@Engineering partner start again'),
    ()=>studio.start(task,'brainstorming','Engineering partner'),
    ()=>studio.selectDelivery('DEL-LATE','Reopen for review.'),
  ];
  for(const change of changes){
    assert.throws(change,/Restore this archived issue/);
    assert.equal(JSON.stringify(studio.db),before);
  }
  studio.restoreIssues([task.id]);
  studio.transitionIssue(task,'todo',{handoff:false});
  assert.equal(task.status,'todo');
});

test('archive batches are workspace-local and cannot affect matching IDs in another workspace',()=>{
  const {studio}=workspace(),task=completed(studio);
  studio.archiveIssues([task.id]);
  const other=studio.createWorkspace('Archive isolation');
  studio.selectWorkspace(other);
  assert.throws(()=>studio.restoreIssues([task.id]),/unavailable in this workspace/);
  studio.db.tasks.push({...JSON.parse(JSON.stringify(task)),archivedAt:undefined,activity:[]});
  studio.save();
  assert.equal(studio.restoreIssues([task.id]).length,0);
  studio.selectWorkspace('tap');
  assert.ok(studio.db.tasks.find(item=>item.id===task.id).archivedAt);
});

test('queued work cannot begin on an archived issue but historical runs can be closed',()=>{
  const {studio}=workspace(),task=completed(studio);
  const queued=studio.start(task,'brainstorming','Engineering partner',true);
  const running=studio.start(task,'webapp-testing','Quality partner');
  studio.archiveIssues([task.id]);
  assert.throws(()=>studio.changeRun(queued,'claim'),/Restore this archived issue/);
  assert.equal(queued.status,'queued');
  studio.changeRun(queued,'cancel');
  studio.changeRun(running,'finish','Close the existing record.');
  assert.equal(queued.status,'cancelled');
  assert.equal(running.status,'finished');
  assert.equal(task.status,'done');
  assert.ok(task.archivedAt);
});

test('ten thousand completed issues archive and restore with one save per batch',()=>{
  const {studio,writes}=workspace(),base=completed(studio);
  const tasks=Array.from({length:10000},(_,i)=>({...base,id:'ARCHIVE-'+i,activity:[]}));
  studio.db.tasks.push(...tasks);
  const ids=tasks.map(task=>task.id);
  writes.length=0;
  assert.equal(studio.archiveIssues(ids).length,10000);
  assert.equal(writes.length,1);
  assert.ok(tasks.every(task=>task.status==='done'&&task.archivedAt));
  writes.length=0;
  assert.equal(studio.restoreIssues(ids).length,10000);
  assert.equal(writes.length,1);
  assert.ok(tasks.every(task=>task.status==='done'&&!task.archivedAt));
});

test('storage failures roll back entire archive and restore batches without losing local edits',()=>{
  const {studio,values,localStorage}=workspace(),first=completed(studio),second=completed(studio,'TAP-SECOND');
  studio.save();
  first.title='An unsaved title edit';
  studio.db.notes.push({text:'An unsaved review note'});
  const ids=[first.id,second.id],before=JSON.stringify(studio.db),stored=values.get('workpal.studio.v2'),setItem=localStorage.setItem;
  localStorage.setItem=()=>{throw Error('Quota exceeded');};
  assert.throws(()=>studio.archiveIssues(ids),/Browser storage could not save.*No issues were archived/);
  assert.equal(JSON.stringify(studio.db),before);
  assert.equal(values.get('workpal.studio.v2'),stored);
  localStorage.setItem=setItem;
  studio.archiveIssues(ids);
  const archived=JSON.stringify(studio.db),archivedStored=values.get('workpal.studio.v2');
  localStorage.setItem=()=>{throw Error('Storage unavailable');};
  assert.throws(()=>studio.restoreIssues(ids),/Browser storage could not save.*No issues were restored/);
  assert.equal(JSON.stringify(studio.db),archived);
  assert.equal(values.get('workpal.studio.v2'),archivedStored);
  localStorage.setItem=setItem;
  assert.equal(studio.restoreIssues(ids).length,2);
  assert.equal(first.title,'An unsaved title edit');
  assert.equal(studio.db.notes.at(-1).text,'An unsaved review note');
});

test('persistence conflicts roll back archive changes while preserving the conflict for the UI',()=>{
  const {studio,values}=workspace(),task=completed(studio);
  studio.save();
  const remote=JSON.parse(values.get('workpal.studio.v2'));
  remote.tasks.find(item=>item.id===task.id).title='Title from another tab';
  values.set('workpal.studio.v2',JSON.stringify(remote));
  const before=JSON.stringify(studio.db);
  assert.throws(()=>studio.archiveIssues([task.id]),error=>error.code==='WORKSPACE_CONFLICT');
  assert.equal(JSON.stringify(studio.db),before);
  assert.equal(JSON.parse(values.get('workpal.studio.v2')).tasks.find(item=>item.id===task.id).title,'Title from another tab');
});
