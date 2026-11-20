import {createIssueParentEditor} from './issue-parent.js';
import {el} from '../ui.js';
export function createIssueHierarchy({client,issue,actions,current,onError,onNavigate,onChanged}) {
 const section=el('section',undefined,{'aria-label':'Issue hierarchy'}),parent=el('div'),rows=el('div'),notice=el('p','',{role:'status'});
 let generation=0,cursor=0,items=[];
 const button=(name,fn)=>{const b=el('button',name,{type:'button'});b.onclick=fn;return b;};
 const link=fact=>button(`${fact.title} (#${fact.id})`,()=>{if(current())onNavigate(fact.id);});
 async function call(action,payload,token){const result=await client.perform(action,payload,{current:()=>current()&&token===generation});if(result.state!=='completed')throw Error('Request not confirmed. Please retry.');return result.data;}
 function fail(error,token,retry){if(!current()||token!==generation||error.code==='context_changed')return;if([403,404].includes(error.status)){++generation;items=[];cursor=0;section.replaceChildren();onError(error);return;}notice.replaceChildren(el('span',error.message,{role:'alert'}),button('Retry',retry));}
 const archived=el('input',undefined,{type:'checkbox','aria-label':'Include archived subtasks'});
 const more=button('Load more subtasks',()=>load(true));more.hidden=true;
 async function load(append=false){const token=++generation,start=append?cursor:0,focusMore=append&&document.activeElement===more,previousCount=items.length;more.hidden=true;notice.textContent='Loading hierarchy…';if(!append){items=[];rows.replaceChildren();parent.replaceChildren();cursor=0;}
 try{const latest=await call('issue.read',{issue_id:issue.id},token);if(!current()||token!==generation)return;const [fact,page]=await Promise.all([latest.parent_issue_id?call('issue.read',{issue_id:latest.parent_issue_id},token):Promise.resolve(null),call('issue.children.list',{issue_id:issue.id,cursor:start,limit:20,include_archived:archived.checked},token)]);if(!current()||token!==generation)return;
 parent.replaceChildren(fact?link(fact):el('p','No parent issue.'));items=append?[...items,...page.items]:page.items;cursor=page.next_cursor;rows.replaceChildren();for(const item of items){const row=el('div',undefined,{class:'project-row'});row.append(link(item),el('span',item.status_key));rows.append(row);}notice.textContent=items.length?'':'No visible subtasks.';more.hidden=!cursor;if(focusMore&&(document.activeElement===document.body||document.activeElement===more))rows.children[previousCount]?.querySelector('button')?.focus();
 }catch(error){fail(error,token,()=>load(append));}}
 if(actions.includes('issue.set_parent')){const editor=createIssueParentEditor({client,issue,current,onError,onChanged});section.append(button('Change parent',event=>editor.open(event.currentTarget)));}
 const refresh=button('Refresh hierarchy',()=>load());
 const show=button('Show hierarchy',()=>{show.hidden=true;refresh.focus();load();});archived.onchange=()=>load();section.append(show,el('h3','Parent issue'),parent,el('h3','Subtasks'),el('label','Include archived subtasks'),archived,refresh,notice,rows,more);return section;
}
