import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const source=readFileSync(new URL('../src/issues-workflow.js',import.meta.url),'utf8');
const states={backlog:'Backlog',todo:'To do',active:'In progress',review:'In review',blocked:'Blocked',done:'Done'};
function load(db){
  const ctx=vm.createContext({WorkpalStudio:{states},document:{addEventListener(){}},MouseEvent:class{}});
  vm.runInContext(source,ctx);
  const api=ctx.WorkpalIssueFlow;
  api.init({getDb:()=>db,workspace:()=>({id:'test'}),esc:value=>String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;'),icon:()=>'',render(){}});
  return api;
}
test('workflow overview follows project review destinations, not implementation next',()=>{
  const db={projects:['App'],projectSettings:[{project:'App',workflowId:'custom'}],workflows:[{id:'custom',name:'Custom',steps:[{status:'active',next:'done'},{status:'review',next:'todo',rejected:'blocked'}]}]};
  const api=load(db),flow=api.describe(db,'App');
  assert.equal(flow.approved,'todo');
  assert.equal(flow.rejected,'blocked');
  assert.equal(flow.gated,false);
  const markup=api.page();
  assert.match(markup,/Submit delivery/);
  assert.match(markup,/Approve → To do/);
  assert.match(markup,/Request changes → Blocked/);
  assert.match(markup,/Restore to Done/);
});
test('merge and acceptance rules add a gate only when review would complete',()=>{
  for(const completion of ['merged','acceptance']){
    const db={projects:['App'],projectSettings:[{project:'App',deliveryRules:{completion}}],workflows:[]};
    const api=load(db);
    assert.equal(api.describe(db,'App').gated,true);
    assert.match(api.page(),/data-issue-flow-node="gate"/);
    assert.match(api.page(),/In review until delivery checks are complete/);
    db.workflows.push({id:'custom',name:'Custom',steps:[{status:'review',next:'todo'}]});
    db.projectSettings[0].workflowId='custom';
    assert.equal(api.describe(db,'App').gated,false);
    assert.doesNotMatch(api.page(),/data-issue-flow-node="gate"/);
  }
});
test('empty workspace has safe defaults and custom workflow text stays escaped',()=>{
  const empty=load({projects:[],projectSettings:[],workflows:[]});
  assert.match(empty.page(),/Default workflow/);
  assert.match(empty.page(),/Request changes → In progress/);
  const value='<img src=x onerror=alert(1)>';
  const db={projects:[value],projectSettings:[{project:value,workflowId:'custom',lead:value}],workflows:[{id:'custom',name:value,steps:[{status:'review',owner:'Project lead',instructions:value}]}]};
  const html=load(db).page();
  assert.doesNotMatch(html,/<img/);
  assert.match(html,/&lt;img/);
});
