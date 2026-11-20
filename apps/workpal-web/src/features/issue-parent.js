import {el,openDialog} from '../ui.js';
export function createIssueParentEditor({client,issue,current,onError,onChanged}) {
 let baseline=issue,selected=null,intent=null,conflict=false,generation=0,queryText='';
 const button=(label,fn)=>{const b=el('button',label,{type:'button'});b.onclick=fn;return b;};
 function open(returnFocus){
  const token=++generation,form=el('form',undefined,{class:'issue-composer'}),dialog=openDialog(form,{returnFocus,label:'Change parent'});
  dialog.classList.add('issue-create-dialog');
  const valid=()=>current()&&token===generation&&dialog.open;
  let busy=false,sequence=0,cursor=0;
  const controls=el('fieldset'),rows=el('div'),error=el('p','',{role:'alert'}),selection=el('p'),fact=el('p'),query=el('input',undefined,{type:'search','aria-label':'Search parent issues'});
  query.value=queryText;
  const submit=el('button','Save parent',{type:'submit'}),more=button('Load more issues',()=>search(true));
  const remove=button('Remove parent',()=>{selected=0;sync();});
  const reload=button('Reload current',async()=>{busy=true;sync();try{baseline=await call('issue.read',{issue_id:issue.id});if(baseline.parent_issue_id){const parent=await call('issue.read',{issue_id:baseline.parent_issue_id});if(valid())fact.textContent=`Current parent: ${parent.title} (#${parent.id})`;}else fact.textContent='No parent issue.';if(valid()){conflict=false;error.textContent=selected===baseline.parent_issue_id?'The selected parent is already current. Refresh the issue to finish.':'Review your selection and submit again.';}}catch(e){fail(e);}finally{if(valid()){busy=false;sync();}}});
  const refresh=button('Refresh issue',()=>{if(!valid())return;dialog.close();onChanged();});
  function sync(){controls.disabled=busy||!!intent;submit.disabled=busy||conflict||selected===null||(!intent&&selected===baseline?.parent_issue_id);submit.textContent=intent?'Retry original request':'Save parent';refresh.hidden=conflict||selected===null||selected!==baseline?.parent_issue_id;reload.hidden=!conflict;reload.disabled=busy;selection.textContent=selected===null?'Select a parent issue.':selected===0?'Remove parent selected.':`Selected parent: #${selected}`;}
  async function call(action,payload,options={}){const r=await client.perform(action,payload,{...options,current:()=>valid()&&(!options.current||options.current())});if(r.state!=='completed')throw Error('Request not confirmed. Please retry.');return r.data;}
  function fail(e){if(!valid()||e.code==='context_changed')return;if([403,404].includes(e.status)){selected=null;intent=null;baseline=null;queryText='';rows.replaceChildren();dialog.close();onError(e);return;}error.textContent=e.message;}
  async function search(append=false){const request=++sequence,focusMore=append&&document.activeElement===more,previousCount=rows.childElementCount;queryText=query.value;if(!append){cursor=0;rows.replaceChildren();}if(!append)more.hidden=true;try{const page=await call('issue.list',{query:queryText,cursor,limit:20,include_archived:false},{current:()=>request===sequence});if(!valid()||request!==sequence)return;for(const candidate of page.items){if(candidate.id===issue.id)continue;rows.append(button(`${candidate.title} (#${candidate.id})`,()=>{selected=candidate.id;sync();}));}cursor=page.next_cursor;const restore=focusMore&&document.activeElement===more;more.hidden=!cursor;if(restore)rows.children[previousCount]?.focus();}catch(e){if(request===sequence)fail(e);}}
  query.oninput=()=>search();
  controls.append(query,rows,more,remove);form.append(el('h2','Change parent'),fact,selection,controls,error,submit,reload,refresh,button('Cancel',()=>dialog.close()));
  dialog.addEventListener('close',()=>{if(token===generation)++generation;});
  form.onsubmit=async event=>{event.preventDefault();if(!valid()||submit.disabled)return;intent??=Object.freeze({payload:Object.freeze({issue_id:issue.id,parent_issue_id:selected}),revision:baseline.revision,key:crypto.randomUUID()});const frozen=intent;busy=true;sync();try{await call('issue.set_parent',frozen.payload,{revision:frozen.revision,key:frozen.key});const fresh=await call('issue.read',{issue_id:issue.id});if(!valid())return;baseline=fresh;intent=null;dialog.close();onChanged();}catch(e){if(!valid())return;if(e.status===409){intent=null;conflict=true;}else if(e.status===400)intent=null;fail(e);}finally{if(valid()){busy=false;sync();}}};
  async function loadFact(){busy=true;sync();try{baseline=await call('issue.read',{issue_id:issue.id});if(baseline.parent_issue_id){const parent=await call('issue.read',{issue_id:baseline.parent_issue_id});if(valid())fact.textContent=`Current parent: ${parent.title} (#${parent.id})`;}else if(valid())fact.textContent='No parent issue.';}catch(e){fail(e);}finally{if(valid()){busy=false;sync();}}}
  if(!intent)loadFact();
  if(intent)error.textContent='Outcome is unknown. Retry the original request.';sync();if(!intent)search();
 }
 return {open};
}
