import {el} from '../ui.js';
const button=(name,fn)=>{const b=el('button',name,{type:'button'});b.onclick=fn;return b;};
export function createPersonLabel({client,userId,current,onError}) {
  const root=el('span',undefined,{class:'person-label'}); let sequence=0;
  async function load(){
    const token=++sequence;
    if(!userId){root.textContent='Unassigned';return;}
    root.textContent='Loading person…';
    try {
      const result=await client.perform('workspace.people.read',{user_id:userId});
      if(!current() || token!==sequence)return;
      if(result.state!=='completed')throw Error('Reading has not been confirmed.');
      root.textContent=result.data.person ? `${result.data.person.username} (#${userId})` : `Unavailable person (#${userId})`;
    }catch(e){if(!current() || token!==sequence)return;if([403,404].includes(e.status)){onError(e);return;}root.replaceChildren(el('span',e.message),button('Retry',load));}
  }
  load();return root;
}
export function createPersonPicker({client,value,current,onChange,onError,heading='Assignee'}) {
  const root=el('section'), chosen=el('p'), rows=el('div'), status=el('p','',{role:'status'});
  const search=el('input',undefined,{type:'search','aria-label':'Search people',placeholder:'Search people',maxlength:'150'});
  let cursor=0,sequence=0,selected=value;
  function paint(){const id=selected;chosen.replaceChildren(createPersonLabel({client,userId:id,current:()=>current()&&selected===id,onError}));}
  function select(id){selected=id;paint();onChange(id);}
  const more=button('Load more people',()=>load(true));
  async function load(append=false){const token=++sequence;if(!append){cursor=0;rows.replaceChildren();}more.hidden=true;status.textContent='Loading people…';
    try{const result=await client.perform('workspace.people.list',{query:search.value,cursor,limit:20});if(!current()||token!==sequence)return;if(result.state!=='completed')throw Error('Reading has not been confirmed.');
      for(const person of result.data.items){const row=el('div',undefined,{class:'issue-picker-option'});row.append(button(`${person.username} (#${person.user_id})`,()=>select(person.user_id)));rows.append(row);}
      cursor=result.data.next_cursor;more.hidden=!cursor;status.textContent=rows.childElementCount?'':'No results found.';
    }catch(e){if(!current()||token!==sequence)return;if([403,404].includes(e.status)){onError(e);return;}status.replaceChildren(el('span',e.message),button('Retry',()=>load(append)));}}
  if(heading)root.append(el('h3',heading));
  root.append(button('Unassigned',()=>select(0)),search,chosen,status,rows,more);search.oninput=()=>load();paint();load();return root;
}
