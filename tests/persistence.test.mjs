import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {randomUUID} from 'node:crypto';

const scripts=['data','model'].map(name=>readFileSync(new URL('../src/'+name+'.js',import.meta.url),'utf8'));
function sharedStorage(){
  const values=new Map();
  return {get length(){return values.size;},key:i=>[...values.keys()][i],getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value)};
}
function tab(localStorage){
  const ctx=vm.createContext({localStorage,crypto:{randomUUID}});
  for(const script of scripts)vm.runInContext(script,ctx);
  return ctx.WorkpalStudio;
}
const persisted=storage=>JSON.parse(storage.getItem('workpal.studio.v2'));
const note=(text,at=101)=>({page:'Settings',author:'Reviewer',text,at});

test('two stale tabs append review notes without overwriting either note',()=>{
  const storage=sharedStorage(),first=tab(storage),second=tab(storage);
  first.db.notes.unshift(note('First review',101));first.save();
  second.db.notes.unshift(note('Second review',101));second.save();
  assert.deepEqual(persisted(storage).notes.map(n=>n.text).sort(),['First review','Second review']);
  assert.equal(second.db.notes.length,2);
  first.save();
  assert.equal(first.db.notes.length,2);
  assert.equal(persisted(storage).notes.length,2);
});

test('a stale task edit and a newer note both survive either write order',()=>{
  for(const noteFirst of [true,false]){
    const storage=sharedStorage(),first=tab(storage),second=tab(storage);
    const task=first.db.tasks[0],id=task.id;
    task.description='An independently updated task';
    second.db.notes.unshift(note('Keep the reviewer note'));
    if(noteFirst){second.save();first.save();}else{first.save();second.save();}
    const saved=persisted(storage);
    assert.equal(saved.tasks.find(t=>t.id===id).description,'An independently updated task');
    assert.equal(saved.notes[0].text,'Keep the reviewer note');
    // Model methods keep referencing the same task object after a merge.
    assert.equal(first.db.tasks.find(t=>t.id===id),task);
    task.priority='Urgent';first.save();
    assert.equal(persisted(storage).tasks.find(t=>t.id===id).priority,'Urgent');
    assert.equal(persisted(storage).notes[0].text,'Keep the reviewer note');
  }
});

test('edits to different task records merge without losing either change',()=>{
  const storage=sharedStorage(),first=tab(storage),second=tab(storage);
  const firstId=first.db.tasks[0].id,secondId=second.db.tasks[1].id;
  first.db.tasks[0].title='First task edit';first.save();
  second.db.tasks[1].title='Second task edit';second.save();
  const saved=persisted(storage);
  assert.equal(saved.tasks.find(t=>t.id===firstId).title,'First task edit');
  assert.equal(saved.tasks.find(t=>t.id===secondId).title,'Second task edit');
});

test('concurrent edits to the same task reject the stale save and preserve both versions',()=>{
  const storage=sharedStorage(),first=tab(storage),second=tab(storage);
  const id=first.db.tasks[0].id;
  first.db.tasks[0].description='Saved by tab one';first.save();
  second.db.tasks[0].description='Unsaved edit in tab two';
  const before=storage.getItem('workpal.studio.v2');
  assert.throws(()=>second.save(),error=>error.code==='WORKSPACE_CONFLICT'&&/another tab/.test(error.message));
  assert.equal(storage.getItem('workpal.studio.v2'),before);
  assert.equal(second.db.tasks[0].description,'Unsaved edit in tab two');
  assert.equal(persisted(storage).tasks.find(t=>t.id===id).description,'Saved by tab one');
});

test('concurrent run identifiers cannot overwrite a different newly created run',()=>{
  const storage=sharedStorage(),first=tab(storage),second=tab(storage);
  first.db.runs.unshift({id:'RUN-999',task:'A',status:'queued'});first.save();
  second.db.runs.unshift({id:'RUN-999',task:'B',status:'queued'});
  assert.throws(()=>second.save(),error=>error.code==='WORKSPACE_CONFLICT');
  assert.equal(persisted(storage).runs.find(r=>r.id==='RUN-999').task,'A');
  assert.equal(second.db.runs.find(r=>r.id==='RUN-999').task,'B');
});

test('workspace selection resets the merge baseline and isolates records',()=>{
  const storage=sharedStorage(),first=tab(storage),second=tab(storage);
  const other=first.createWorkspace('Persistence test');
  assert.equal(first.selectWorkspace(other),true);
  first.db.notes.unshift(note('Other workspace'));first.save();
  second.db.notes.unshift(note('Home workspace'));second.save();
  assert.equal(first.selectWorkspace('tap'),true);
  assert.equal(first.db.notes[0].text,'Home workspace');
  first.db.notes.unshift(note('More home notes'));first.save();
  assert.equal(second.selectWorkspace(other),true);
  assert.equal(second.db.notes.length,1);
  assert.equal(second.db.notes[0].text,'Other workspace');
  second.db.notes.unshift(note('Second other note'));second.save();
  assert.equal(first.selectWorkspace(other),true);
  assert.equal(first.db.notes.length,2);
  assert.equal(persisted(storage).notes.length,2);
});
