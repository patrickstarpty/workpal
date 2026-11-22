import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {randomUUID} from 'node:crypto';

function setup(previous){
  const values=new Map(previous?[['workpal.studio.v2',JSON.stringify(previous)]]:[]);
  const localStorage={get length(){return values.size;},key:i=>[...values.keys()][i],getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value)};
  const ctx=vm.createContext({localStorage,crypto:{randomUUID}});
  for(const name of ['data','model','environment-chat'])vm.runInContext(readFileSync(new URL('../src/'+name+'.js',import.meta.url),'utf8'),ctx);
  const s=ctx.WorkpalStudio,e=ctx.WorkpalEnvironmentChat;
  s.db.conversations??=[];
  return {s,e,values};
}
const plain=value=>JSON.parse(JSON.stringify(value));

test('authored environment histories are idempotent and preserve user conversations, notes and selection',()=>{
  const {s,e}=setup(),c={id:'existing',title:'My notes',agent:'Product partner',messages:[{role:'user',text:'Keep this'}],draft:'Unsent text'};
  s.db.conversations.push(c);s.db.currentChat=c.id;s.db.notes.push({text:'Reviewer note'});
  const runs=s.db.runs.length;
  assert.equal(e.initialize(s.db,'tap'),true);
  assert.equal(s.db.conversations.length,4);assert.equal(s.db.currentChat,'existing');
  assert.equal(s.db.conversations[0],c);assert.equal(c.draft,'Unsent text');
  for(const item of s.db.conversations.slice(1)){
    assert.equal(item.messages.length,6);assert.equal(item.fixtureSource,'environment-chat-v1');
    assert.ok(item.messages.every(m=>m.fixtureSource===item.fixtureSource && m.agent===item.agent && m.environment===item.environment));
    assert.ok(item.messages.filter(m=>m.role==='assistant').some(m=>/hypothesis|unconfirmed|not.*confirmed|not.*prove/.test(m.text)));
  }
  assert.equal(s.db.runs.length,runs);assert.equal(s.db.notes[0].text,'Reviewer note');
  assert.equal(e.initialize(s.db,'tap'),false);assert.equal(s.db.conversations.length,4);
  s.save();const reopened=setup(s.db);
  assert.equal(reopened.e.initialize(reopened.s.db,'tap'),false);
  assert.equal(reopened.s.db.conversations[0].draft,'Unsent text');
});

test('initialization preserves colliding authored IDs and leaves custom workspaces empty',()=>{
  const {s,e}=setup();
  const existing={id:'environment-chat-uat',title:'User-authored title',messages:[]};s.db.conversations.push(existing);
  e.initialize(s.db,'tap');assert.equal(s.db.conversations.find(c=>c.id===existing.id),existing);
  const id=s.createWorkspace('Environment isolation');assert.equal(s.selectWorkspace(id),true);s.db.conversations=[];
  assert.equal(e.initialize(s.db,id),false);assert.equal(s.db.conversations.length,0);assert.equal(s.db.agents.length,0);
  assert.equal(s.db.environmentChatVersion,undefined);
});

test('environment queue captures independent context, routes the selected agent and produces no assistant answer',()=>{
  const {s,e}=setup();e.initialize(s.db,'tap');
  const c=s.db.conversations.find(c=>c.environment==='UAT'),other=s.db.conversations.find(c=>c.environment==='PRD');
  c.agent='Architecture partner';
  const settings=s.db.projectSettings.find(p=>p.project==='TAP');settings.resources=[{name:'Code',url:'https://example.test/code'}];
  const originalLength=c.messages.length,otherHistory=JSON.stringify(other.messages),text='<img src=x onerror=alert(1)>\nTrace excerpt: "up_731"';
  const r=e.queue(s.db,c,'  '+text+'  ');
  assert.equal(r.status,'queued');assert.equal(r.mode,'offline');assert.equal(r.agent,'Architecture partner');
  assert.equal(r.context.environment,'UAT');assert.equal(r.context.project,'TAP');
  assert.equal(c.messages.length,originalLength+1);assert.equal(c.messages.at(-1).role,'user');
  assert.equal(c.messages.at(-1).text,text);assert.equal(c.messages.at(-1).run,r.id);
  assert.equal(r.context.conversation.messages.at(-1).text,text);assert.equal(JSON.stringify(other.messages),otherHistory);
  c.environment='PRD';c.agent='Engineering partner';c.messages[0].text='Edited history';c.messages.at(-1).queued=false;
  settings.resources[0].name='Edited resource';s.db.agents.find(a=>a.name==='Architecture partner').role='Changed role';
  assert.equal(r.context.environment,'UAT');assert.notEqual(r.context.conversation.messages[0].text,'Edited history');
  assert.equal(r.context.conversation.messages.at(-1).queued,true);assert.equal(r.context.projectSettings.resources[0].name,'Code');
  assert.notEqual(r.context.agent.role,'Changed role');
  const second=e.queue(s.db,other,'A separate production follow-up');
  assert.notEqual(r.id,second.id);assert.equal(second.context.environment,'PRD');
});

test('invalid environment requests leave runs and message history untouched',()=>{
  const {s,e}=setup();e.initialize(s.db,'tap');const c=s.db.conversations[0];
  const before=JSON.stringify({runs:s.db.runs,messages:c.messages});
  assert.throws(()=>e.queue(s.db,c,'  '),/message/);
  const values={environment:c.environment,agent:c.agent,project:c.project};
  for(const [key,value,pattern] of [['environment','missing',/environment/],['agent','missing',/agent/],['project','missing',/project/]]){
    c[key]=value;assert.throws(()=>e.queue(s.db,c,'Investigate'),pattern);c[key]=values[key];
  }
  assert.throws(()=>e.queue(s.db,{...c},'Investigate'),/workspace/);
  assert.equal(JSON.stringify({runs:s.db.runs,messages:c.messages}),before);
  assert.equal(e.profile('PRD').agentName,'Engineering partner');assert.equal(e.agent(s.db,'UAT').name,'Quality partner');
});

test('issue handoff retains context and history, creates no run, and reuses the linked backlog issue',()=>{
  const {s,e,values}=setup();e.initialize(s.db,'tap');
  const c=s.db.conversations.find(c=>c.environment==='PRD'),count=s.db.tasks.length,runs=s.db.runs.length;
  const t=e.createIssue(s,c);
  assert.equal(t.status,'backlog');assert.equal(t.owner,c.agent);assert.equal(t.project,'TAP');
  assert.equal(t.environment,'PRD');assert.equal(t.conversationId,c.id);assert.equal(c.issueId,t.id);
  assert.ok(t.tags.includes('PRD'));assert.equal(t.conversationSnapshot.conversation.fixtureSource,'environment-chat-v1');
  assert.match(t.description,/req_k9m2/);assert.match(t.description,/Neither action is approved or executed here/);
  assert.equal(s.db.runs.length,runs);assert.equal(s.db.tasks.length,count+1);
  c.messages.push({role:'user',text:'A later note',environment:'PRD',agent:c.agent});
  assert.equal(e.createIssue(s,c).id,t.id);assert.equal(s.db.tasks.length,count+1);
  assert.ok(!t.conversationSnapshot.conversation.messages.some(m=>m.text==='A later note'));
  const stored=JSON.parse(values.get('workpal.studio.v2'));
  assert.equal(stored.conversations.find(x=>x.id===c.id).issueId,t.id);
  assert.equal(stored.tasks.find(x=>x.id===t.id).environment,'PRD');
  const reopened=setup(stored),restored=reopened.s.db.conversations.find(x=>x.id===c.id);
  assert.equal(reopened.e.createIssue(reopened.s,restored).id,t.id);
});

test('a new custom-workspace investigation can use an explicitly configured agent without adding fixtures',()=>{
  const {s,e}=setup(),id=s.createWorkspace('Incident team');s.selectWorkspace(id);
  s.db.projects.push('Service');s.db.agents.push({name:'Incident owner',role:'Triage',skills:[],runtime:'Local runner'});
  const c={id:'custom-chat',environment:'PRD',agent:'Incident owner',project:'Service',title:'Service errors',messages:[]};s.db.conversations=[c];
  assert.equal(e.initialize(s.db,id),false);
  assert.throws(()=>e.createIssue(s,c),/problem/);
  const r=e.queue(s.db,c,'Gateway log: upstream timeout');assert.equal(r.agent,'Incident owner');
  const t=e.createIssue(s,c);assert.equal(t.owner,'Incident owner');assert.equal(t.project,'Service');
  assert.ok(!t.description.includes('Authored conversation example'));assert.equal(s.db.conversations.length,1);
  assert.deepEqual(plain(t.conversationSnapshot.conversation.messages).map(m=>m.text),['Gateway log: upstream timeout']);
});
