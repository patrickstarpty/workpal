import {el} from '../ui.js';
import {createPersonLabel} from './people.js';

export function createIssueTransitionHistory({client,issue,current,onError}) {
  const id=issue.id, snapshot=structuredClone(issue.workflow_snapshot);
  const root=el('section',undefined,{class:'issue-status-history','aria-label':'Status history'});
  const button=(text,fn)=>{const b=el('button',text,{type:'button'});b.onclick=fn;return b;};
  let expanded=false, sequence=0, cursor=0, loading=false;
  const rows=el('div'), status=el('p',undefined,{role:'status'});
  const toggle=button('Show status history',()=>{
    expanded=!expanded; ++sequence;
    toggle.textContent=expanded?'Hide status history':'Show status history';
    toggle.setAttribute('aria-expanded',String(expanded));
    rows.replaceChildren();status.replaceChildren();refresh.hidden=more.hidden=!expanded;
    if(expanded)load(false);
  });
  toggle.setAttribute('aria-expanded','false');
  const refresh=button('Refresh status history',()=>load(false));
  const more=button('Load more status history',()=>{if(!loading)load(true);});
  refresh.hidden=more.hidden=true;
  const label=(event,key)=>event.workflow_sha256===snapshot.sha256 ? snapshot.definition.states.find(s=>s.key===key)?.label??key : key;
  function row(event,token){
    const node=el('details'), summary=el('summary',`${label(event,event.from_key)} → ${label(event,event.to_key)} · ${event.created_at}`);
    node.append(summary);let painted=false;
    node.addEventListener('toggle',()=>{
      if(!node.open||painted||!valid(token))return;painted=true;
      const fact=(name,value)=>node.append(el('p',`${name}: ${value}`));
      const person=(name,userId)=>{const p=el('p',`${name}: `);p.append(createPersonLabel({client,userId,current:()=>valid(token),onError:accessError}));node.append(p);};
      fact('Issue revision',event.revision);person('Changed by',event.actor_user_id);
      if(event.actor_executor_id)fact('Executor',event.actor_executor_id);
      if(event.reason)fact('Reason',event.reason);
      const blockingChange=event.before_blocked_owner_id||event.after_blocked_owner_id||event.before_blocked_reason||event.after_blocked_reason;
      for(const [prefix,name] of [['before','Previous blocking reason'],['after','Blocking reason']]){
        if(event[`${prefix}_blocked_reason`])fact(name,event[`${prefix}_blocked_reason`]);
        if(blockingChange)person(prefix==='before'?'Before blocked owner':'After blocked owner',event[`${prefix}_blocked_owner_id`]);
      }
    });return node;
  }
  const valid=token=>current()&&expanded&&token===sequence;
  function accessError(error){if([403,404].includes(error.status)){++sequence;rows.replaceChildren();status.replaceChildren();more.hidden=true;}onError(error);}
  async function load(append){
    const token=append?sequence:++sequence;
    if(!append){cursor=0;rows.replaceChildren();}
    loading=true;more.disabled=true;more.hidden=true;status.textContent='Loading status history…';
    try{
      const result=await client.perform('issue.transitions.list',{issue_id:id,cursor,limit:20});
      if(!valid(token))return;
      if(result.state!=='completed')throw Error('Reading has not been confirmed. Please retry.');
      for(const event of result.data.items)rows.append(row(event,token));
      cursor=result.data.next_cursor;more.hidden=!cursor;
      status.textContent=rows.childElementCount?'':'No status changes.';
    }catch(error){
      if(!valid(token))return;
      if([403,404].includes(error.status)){accessError(error);return;}
      status.replaceChildren(el('span',error.message),button('Retry',()=>{if(!loading)load(append);}));
    }finally{if(valid(token)){loading=false;more.disabled=false;}}
  }
  root.append(el('h2','Status history'),toggle,refresh,status,rows,more);return root;
}
