import {createPersonPicker} from './people.js';
import {el,openDialog} from '../ui.js';
export function createIssueTransitionEditor({client,issue,current,onError,onChanged}) {
 let baseline=issue,target='',reason='',owner=0,intent=null,conflict=false,generation=0;
 return {open(returnFocus){
 const token=++generation;let busy=false,role=null;
 const form=el('form',undefined,{class:'issue-composer'}),dialog=openDialog(form,{returnFocus,label:'Change status'});
 dialog.classList.add('issue-create-dialog');
 const valid=()=>current()&&dialog.open&&token===generation;
 dialog.addEventListener('close',()=>{if(token===generation)generation++;});
 const facts=el('p'),error=el('p','',{role:'alert'}),permission=el('p'),controls=el('fieldset');
 const select=el('select',undefined,{'aria-label':'Target status'}),text=el('textarea',reason,{'aria-label':'Reason',maxlength:'4000'});
 const blocked=el('fieldset'),legend=el('legend','Blocked owner');blocked.append(legend,createPersonPicker({client,value:owner,current:valid,onError,heading:'',onChange:v=>{owner=v;sync();}}));
 const button=(name,fn)=>{const b=el('button',name,{type:'button'});b.onclick=fn;return b;};
 const save=el('button','Save status',{type:'submit'});
 const state=()=>baseline.workflow_snapshot.definition.states.find(s=>s.key===target);
 const targets=()=>baseline.workflow_snapshot.definition.transitions.filter(t=>t.from===baseline.status_key).map(t=>t.to);
 function paint(){const states=baseline.workflow_snapshot.definition.states;facts.textContent=`Status: ${states.find(s=>s.key===baseline.status_key)?.label??baseline.status_key}`;select.replaceChildren(el('option','Select target',{value:''}));for(const key of new Set(targets())){const s=states.find(s=>s.key===key);select.append(el('option',`${s.label} (${key})`,{value:key}));}if(target&&!targets().includes(target)&&target!==baseline.status_key){select.append(el('option',`Unavailable (${target})`,{value:target,disabled:''}));}select.value=target;if(!targets().length)error.textContent='No available transitions';}
 function sync(){const category=state()?.category;blocked.hidden=category!=='blocked';const done=category==='done',allowed=baseline.workflow_snapshot.definition.review_policy.reviewer_roles.includes(role);permission.textContent=done?(role===null?'Checking reviewer permissions':allowed?'':'Human reviewer required'):'';controls.disabled=busy||!!intent;save.textContent=intent?'Retry original request':'Save status';save.disabled=busy||conflict||(!intent&&(!target||!targets().includes(target)||target===baseline.status_key||(['blocked','done'].includes(category)&&!reason.trim())||(category==='blocked'&&!(owner>0))||(done&&!allowed)));reload.hidden=!conflict;reload.disabled=busy;refresh.hidden=target!==baseline.status_key;}
 function fail(e){if(!valid()||e.code==='context_changed')return;if([403,404].includes(e.status)){intent=null;reason='';target='';owner=0;dialog.close();onError(e);return;}error.textContent=e.message;}
 async function permissions(){try{const r=await client.perform('workspace.read',{});if(!valid())return;if(r.state!=='completed')throw Error('Permission read not confirmed');role=r.data.role;sync();}catch(e){fail(e);}}
 const retry=button('Retry permissions',permissions);
 const reload=button('Reload current',async()=>{if(!valid()||busy||intent)return;busy=true;sync();try{const r=await client.perform('issue.read',{issue_id:issue.id});if(!valid())return;if(r.state!=='completed')throw Error('Read not confirmed');baseline=r.data;conflict=false;paint();error.textContent=target===baseline.status_key?'No changes to save':'Review current status before submitting.';}catch(e){fail(e);}finally{if(valid()){busy=false;sync();}}});
 const refresh=button('Refresh issue',()=>{if(valid()&&!busy){dialog.close();onChanged();}});
 select.onchange=()=>{target=select.value;sync();};text.oninput=()=>{reason=text.value;sync();};
 controls.append(el('label','Target status'),select,el('label','Reason'),text,blocked);
 form.append(el('h2','Change status'),facts,controls,permission,retry,error,save,reload,refresh,button('Cancel',()=>dialog.close()));paint();if(intent)error.textContent='Outcome is unknown. Retry the original request.';sync();permissions();
 form.onsubmit=async e=>{e.preventDefault();if(!valid()||save.disabled)return;intent??={payload:{issue_id:issue.id,target,reason,blocked_owner_user_id:state()?.category==='blocked'?owner:0},revision:baseline.revision,key:crypto.randomUUID()};busy=true;sync();try{const r=await client.perform('issue.transition',intent.payload,{revision:intent.revision,key:intent.key});if(!valid())return;if(r.state!=='completed')throw Error('Outcome is unknown. Retry the original request.');intent=null;dialog.close();onChanged();}catch(e){if(!valid())return;if(e.status===409){intent=null;conflict=true;}else if(e.status===400)intent=null;fail(e);}finally{if(valid()){busy=false;sync();}}};return dialog;
 }};
}
