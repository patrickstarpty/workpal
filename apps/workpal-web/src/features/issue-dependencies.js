import {el,openDialog} from '../ui.js';
export function createIssueDependencies({client,issue,actions,current,onError,onChanged}) {
 const section=el('section',undefined,{'aria-label':'Dependencies'}),rows=el('div'),notice=el('p','',{role:'status'});
 let baseline=issue,cursor=0,sequence=0,edges=[],intent=null,dialogGeneration=0;
 const button=(name,fn)=>{const b=el('button',name,{type:'button'});b.onclick=fn;return b;};
 async function call(action,payload,options){const r=await client.perform(action,payload,options);if(r.state!=='completed')throw Error('Request not confirmed. Please retry.');return r.data;}
 function fail(e,target,retry){if(e.code==='context_changed')return;if([403,404].includes(e.status)){intent=null;++sequence;++dialogGeneration;section.replaceChildren();for(const d of dialogs)d.close();onError(e);return;}target.replaceChildren(el('span',e.message,{role:'alert'}));if(retry)target.append(button('Retry',retry));}
 const dialogs=new Set();
 async function fetchPage(start){const data=await call('issue.dependency.list',{issue_id:issue.id,cursor:start,limit:20});const items=[];for(const edge of data.items)items.push({...edge,fact:await call('issue.read',{issue_id:edge.depends_on_id})});return {...data,items};}
 async function load(append=false){const token=++sequence;notice.textContent='Loading dependencies…';more.hidden=true;try{const data=await fetchPage(append?cursor:0);if(!current()||token!==sequence)return;edges=append?[...edges,...data.items]:data.items;cursor=data.next_cursor;paint();notice.textContent=edges.length?'':'No dependencies.';more.hidden=!cursor;}catch(e){if(current()&&token===sequence)fail(e,notice,()=>load(append));}}
 function title(fact){return `${fact.title} (#${fact.id})`;}
 function paint(){rows.replaceChildren();for(const edge of edges){const row=el('div',undefined,{class:'project-row'});const fact=edge.fact,state=fact.workflow_snapshot.definition.states.find(s=>s.key===fact.status_key);row.append(el('span',title(fact)),el('span',state?.label??fact.status_key));if(actions.includes('issue.dependency.remove'))row.append(button('Remove dependency',e=>open('remove',fact,e.currentTarget)));rows.append(row);}}
 const more=button('Load more dependencies',()=>load(true));more.hidden=true;
 const show=button('Show dependencies',()=>{show.hidden=true;refresh.hidden=false;load();}),refresh=button('Refresh dependencies',()=>load());refresh.hidden=true;
 section.append(el('h3','Dependencies'),show,refresh,notice,rows,more);
 if(actions.includes('issue.dependency.add'))section.append(button('Add dependency',e=>open('add',null,e.currentTarget)));
 function open(mode,fact,returnFocus){
  const token=++dialogGeneration;let busy=false,conflict=false,selected=fact?.id??0,searchSequence=0,next=0,absent=false;
  if(intent){mode=intent.mode;selected=intent.payload.depends_on_id;}
  const form=el('form',undefined,{class:'issue-composer'}),dialog=openDialog(form,{returnFocus,label:mode==='add'?'Add dependency':'Remove dependency'});dialogs.add(dialog);dialog.classList.add('issue-create-dialog');
  const valid=()=>current()&&dialog.open&&token===dialogGeneration;
  dialog.addEventListener('close',()=>{dialogs.delete(dialog);if(token===dialogGeneration)++dialogGeneration;});
  const error=el('p','',{role:'alert'}),controls=el('fieldset'),candidates=el('div'),query=el('input',undefined,{type:'search','aria-label':'Search dependency issues',maxlength:'300'});
  const submit=el('button',mode==='add'?'Add dependency':'Remove dependency',{type:'submit'});
  const moreIssues=button('Load more issues',()=>search(true));moreIssues.hidden=true;
  function sync(){controls.disabled=busy||!!intent;submit.textContent=intent?'Retry original request':mode==='add'?'Add dependency':'Remove dependency';submit.disabled=busy||conflict||absent||!selected;reload.hidden=!conflict;reload.disabled=busy;refreshIssue.hidden=!absent;}
  async function search(append=false){const request=++searchSequence;const value=query.value;if(!append){next=0;candidates.replaceChildren();selected=0;sync();}moreIssues.hidden=true;try{const data=await call('issue.list',{query:value,cursor:next,limit:20});if(!valid()||request!==searchSequence)return;for(const item of data.items){if(item.id===issue.id)continue;const pick=button(title(item),()=>{selected=item.id;for(const b of candidates.children)b.setAttribute('aria-pressed',String(b===pick));sync();});pick.setAttribute('aria-pressed',String(item.id===selected));pick.disabled=edges.some(e=>e.depends_on_id===item.id);candidates.append(pick);}next=data.next_cursor;moreIssues.hidden=!next;sync();}catch(e){if(valid()&&request===searchSequence)fail(e,error,()=>search(append));}}
  const reload=button('Reload current',async()=>{if(busy||intent||!valid())return;busy=true;sync();try{const fresh=await call('issue.read',{issue_id:issue.id});let page=await fetchPage(0),all=[...page.items];while(page.next_cursor){page=await fetchPage(page.next_cursor);if(!valid())return;all.push(...page.items);}if(!valid())return;baseline=fresh;edges=all;cursor=0;more.hidden=true;paint();absent=mode==='add'?all.some(e=>e.depends_on_id===selected):!all.some(e=>e.depends_on_id===selected);conflict=false;error.textContent=absent?(mode==='add'?'Dependency already exists.':'Dependency is already removed.'):'Review current dependencies before submitting.';}catch(e){if(valid())fail(e,error);}finally{if(valid()){busy=false;sync();}}});
  const refreshIssue=button('Refresh issue',()=>{dialog.close();onChanged();});
  query.oninput=()=>search();
  if(mode==='add')controls.append(query,candidates,moreIssues);else controls.append(el('p',fact?title(fact):`Issue #${selected}`));
  form.append(el('h2',mode==='add'?'Add dependency':'Remove dependency'),controls,error,submit,reload,refreshIssue,button('Cancel',()=>dialog.close()));
  form.onsubmit=async event=>{event.preventDefault();if(!valid()||submit.disabled)return;intent??={mode,payload:{issue_id:issue.id,depends_on_id:selected},revision:baseline.revision,key:crypto.randomUUID()};const frozen=intent;busy=true;sync();try{await call(`issue.dependency.${frozen.mode}`,frozen.payload,{revision:frozen.revision,key:frozen.key});if(!valid())return;intent=null;dialog.close();onChanged();}catch(e){if(!valid())return;if(e.status===409){intent=null;conflict=true;}else if(e.status===400)intent=null;fail(e,error);}finally{if(valid()){busy=false;sync();}}};
  if(intent)error.textContent='Outcome is unknown. Retry the original request.';sync();if(mode==='add'&&!intent)search();return dialog;
 }
 return section;
}
