import {el,openDialog} from '../ui.js';
export async function showWorkspace({client,content,current,onError,onChange=()=>{}}){
 content.replaceChildren(el('p','Loading workspace…',{role:'status'}));
 try{
 const catalog=await client.catalog(), result=await client.perform('workspace.read',{});if(!current())return;
 if(result.state!=='completed')throw Error('Workspace could not be loaded.');
 let fact=result.data;onChange(fact);content.replaceChildren(el('h1',fact.name),el('p','Your role: '+fact.role));
 if(!catalog.actions.some(a=>a.action_id==='workspace.rename'))return;
 const edit=el('button','Edit workspace');content.append(edit);
 edit.onclick=()=>{
 const form=el('form',undefined,{method:'POST'}),label=el('label','Workspace name'),input=el('input',undefined,{required:'',maxlength:'200'});input.value=fact.name;label.append(input);
 const save=el('button','Save',{type:'submit'}),cancel=el('button','Cancel',{type:'button'}),reload=el('button','Reload workspace',{type:'button'}),msg=el('p',undefined,{role:'alert'});form.append(label,save,cancel,reload,msg);
 const dialog=openDialog(form,{returnFocus:edit,label:'Edit workspace'});cancel.onclick=()=>dialog.close();let intent=null;
 reload.onclick=async()=>{reload.disabled=true;save.disabled=true;try{const r=await client.perform('workspace.read',{});if(!current())return;if(r.state==='completed'){fact=r.data;onChange(fact);content.querySelector('h1').textContent=fact.name;msg.textContent='Current workspace loaded. Your draft is preserved.';intent=null;input.disabled=false;save.textContent='Save';}else{msg.textContent='Workspace could not be loaded. Try again.';}}catch(e){if(current())msg.textContent=e.message;}finally{reload.disabled=false;save.disabled=false;}};
 form.onsubmit=async e=>{e.preventDefault();if(save.disabled)return;intent??={name:input.value,revision:fact.revision,key:crypto.randomUUID()};save.disabled=true;reload.disabled=true;input.disabled=true;
 try{const r=await client.perform('workspace.rename',{name:intent.name},{revision:intent.revision,key:intent.key});if(!current())return;if(r.state==='completed'){fact=r.data;onChange(fact);content.querySelector('h1').textContent=fact.name;dialog.close();}else{msg.textContent='Save has not been confirmed. Reload the workspace to check.';save.textContent='Retry save';}}
 catch(e){if(!current())return;if(e.code==='context_changed')return;if(e.outcome==='unknown'){msg.textContent='Save has not been confirmed. Retry the original save or reload to check.';save.textContent='Retry save';}else{intent=null;input.disabled=false;save.textContent='Save';msg.textContent=e.status===409?'The workspace changed. Your draft is preserved. Reload before saving again.':e.message;}}
 finally{save.disabled=false;reload.disabled=false;}
 };
 };
 }catch(e){if(current())onError(e);}
}
