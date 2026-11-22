import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {randomUUID} from 'node:crypto';

const scripts=['data','integrations','code-delivery','model'].map(name=>readFileSync(new URL('../src/'+name+'.js',import.meta.url),'utf8'));
function storage(){
  const values=new Map();
  return {get length(){return values.size;},key:i=>[...values.keys()][i],getItem:key=>values.get(key)??null,setItem:(key,value)=>values.set(key,value)};
}
function setup(localStorage=storage()){
  const context=vm.createContext({URL,crypto:{randomUUID},localStorage});
  for(const script of scripts)vm.runInContext(script,context);
  return {s:context.WorkpalStudio,api:context.WorkpalIntegrations,localStorage};
}
const copy=value=>JSON.parse(JSON.stringify(value));
const protectedRecords=db=>JSON.stringify({notes:db.notes,tasks:db.tasks,runs:db.runs,projects:db.projectSettings,codeSettings:db.codeSettings});

test('default workspace receives useful repositories and pending accounts once, with deterministic records',()=>{
  const first=setup(),second=setup();
  assert.equal(first.api.initialize(first.s.db,'tap'),true);
  assert.equal(second.api.initialize(second.s.db,'tap'),true);
  assert.equal(first.s.db.integrationFixturesVersion,1);
  assert.equal(first.s.db.repositories.length,5);
  assert.equal(first.s.db.integrationSetups.length,5);
  assert.equal(first.s.db.integrationSetups.filter(a=>a.provider==='jira'&&a.scope==='team').length,2);
  assert.equal(first.s.db.integrationSetups.filter(a=>a.provider==='jira'&&a.scope==='personal').length,1);
  assert.equal(first.s.db.integrationSetups.filter(a=>a.provider==='github').length,2);
  for(const repo of first.s.db.repositories){
    assert.doesNotThrow(()=>first.api.repositoryKey(repo.url));
    assert.ok(repo.description);
    assert.equal(repo.fixtureSource,'integration-settings-v1');
  }
  for(const account of first.s.db.integrationSetups){
    assert.equal(account.status,'authorization-required');
    assert.equal(account.fixtureSource,'integration-settings-v1');
    assert.equal(account.createdBy,'Patrick');
    assert.ok(Number.isFinite(account.createdAt));
    assert.equal(account.token,undefined);
  }
  assert.deepEqual(copy(first.s.db.repositories),copy(second.s.db.repositories));
  assert.deepEqual(copy(first.s.db.integrationSetups),copy(second.s.db.integrationSetups));
  const before=JSON.stringify(first.s.db);
  assert.equal(first.api.initialize(first.s.db,'tap'),false);
  assert.equal(JSON.stringify(first.s.db),before);
});

test('additive migration deduplicates authored entries and preserves unrelated review and delivery records',()=>{
  const {s,api}=setup();
  const repo=api.saveRepository(s.db,{url:'git@GITHUB.COM:PatrickStarPty/Workpal.git',description:'My own repository description'});
  const account=api.saveSetup(s.db,{provider:'jira',scope:'team',name:'tap engineering'});
  api.savePreferences(s.db,{reading:'requested',association:'issue',afterMerge:'complete',prSidebar:false,coAuthor:false});
  s.db.projectSettings[0].resources=[{id:'my-resource',kind:'repository',name:'My code',url:'https://github.com/acme/code',startingRef:'release'}];
  s.db.notes.push({text:'Keep this integration review',author:'Reviewer',at:123});
  const protectedBefore=protectedRecords(s.db),repoBefore=copy(repo),accountBefore=copy(account);
  assert.equal(api.initialize(s.db,'tap'),true);
  assert.equal(s.db.repositories.length,5);
  assert.equal(s.db.integrationSetups.length,5);
  assert.deepEqual(copy(s.db.repositories.find(r=>r.id===repo.id)),repoBefore);
  assert.deepEqual(copy(s.db.integrationSetups.find(a=>a.id===account.id)),accountBefore);
  assert.equal(protectedRecords(s.db),protectedBefore);
});

test('legacy repository values and colliding record IDs cannot overwrite authored records or stop seeding',()=>{
  const baseline=setup();baseline.api.initialize(baseline.s.db,'tap');
  const {s,api}=setup();
  const repo={id:baseline.s.db.repositories[0].id,url:'https://legacy.example.com/repository?ref=main',description:'Historical authored entry'};
  const account={id:baseline.s.db.integrationSetups[0].id,provider:'jira',scope:'personal',name:'Existing custom account',status:'authorization-required',createdBy:'Patrick',createdAt:1};
  s.db.repositories=[repo];s.db.integrationSetups=[account];
  const before={repo:copy(repo),account:copy(account)};
  assert.doesNotThrow(()=>api.initialize(s.db,'tap'));
  assert.equal(s.db.integrationFixturesVersion,1);
  assert.deepEqual(copy(s.db.repositories.find(r=>r.id===repo.id)),before.repo);
  assert.deepEqual(copy(s.db.integrationSetups.find(a=>a.id===account.id)),before.account);
  assert.equal(new Set(s.db.repositories.map(r=>r.id)).size,s.db.repositories.length);
  assert.equal(new Set(s.db.integrationSetups.map(a=>a.id)).size,s.db.integrationSetups.length);
  assert.ok(s.db.repositories.length>1);
  assert.ok(s.db.integrationSetups.length>1);
});

test('fixture edits and deletions persist after reload without being re-created',()=>{
  const {s,api,localStorage}=setup();api.initialize(s.db,'tap');
  const removedRepo=s.db.repositories[0].id,removedAccount=s.db.integrationSetups[0].id;
  const repo=s.db.repositories[1],account=s.db.integrationSetups[1];
  api.saveRepository(s.db,{id:repo.id,url:repo.url,description:'Edited after import'});
  api.saveSetup(s.db,{id:account.id,provider:account.provider,scope:account.scope,name:'My renamed account'});
  api.removeRepository(s.db,removedRepo);api.removeSetup(s.db,removedAccount);s.save();
  const reloaded=setup(localStorage);
  assert.equal(reloaded.api.initialize(reloaded.s.db,'tap'),false);
  assert.equal(reloaded.s.db.repositories.some(r=>r.id===removedRepo),false);
  assert.equal(reloaded.s.db.integrationSetups.some(a=>a.id===removedAccount),false);
  assert.equal(reloaded.s.db.repositories.find(r=>r.id===repo.id).description,'Edited after import');
  assert.equal(reloaded.s.db.integrationSetups.find(a=>a.id===account.id).name,'My renamed account');
});

test('other workspaces remain empty and unchanged while default fixtures survive switching',()=>{
  const {s,api}=setup();api.initialize(s.db,'tap');s.save();
  const home=JSON.stringify({repositories:s.db.repositories,setups:s.db.integrationSetups});
  for(const other of [s.listWorkspaces().find(w=>w.name==='Symphony').id,s.createWorkspace('Integration review')]){
    assert.equal(s.selectWorkspace(other),true);
    const before=JSON.stringify(s.db);
    assert.equal(api.initialize(s.db,other),false);
    assert.equal(JSON.stringify(s.db),before);
    assert.equal(api.repositories(s.db).length,0);
    assert.equal(api.setups(s.db).length,0);
    assert.equal(s.db.integrationFixturesVersion,undefined);
    s.save();
  }
  assert.equal(s.selectWorkspace('tap'),true);
  assert.equal(api.initialize(s.db,'tap'),false);
  assert.equal(JSON.stringify({repositories:s.db.repositories,setups:s.db.integrationSetups}),home);
});

test('two tabs can apply the same deterministic fixture migration without duplicate rows or lost notes',()=>{
  const localStorage=storage(),first=setup(localStorage),second=setup(localStorage);
  first.api.initialize(first.s.db,'tap');second.api.initialize(second.s.db,'tap');
  first.s.db.notes.push({id:'review-one',text:'First reviewer',at:1});
  second.s.db.notes.push({id:'review-two',text:'Second reviewer',at:2});
  assert.equal(first.s.save(),true);
  assert.equal(second.s.save(),true);
  const reloaded=setup(localStorage);
  assert.equal(reloaded.s.db.repositories.length,5);
  assert.equal(reloaded.s.db.integrationSetups.length,5);
  assert.ok(reloaded.s.db.notes.some(n=>n.id==='review-one'));
  assert.ok(reloaded.s.db.notes.some(n=>n.id==='review-two'));
});
