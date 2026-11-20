import {createClient} from './client.js';
import {el} from './ui.js';
import {showIssues} from './features/issues.js';
import {showProjects} from './features/projects.js';
import {showWorkspace} from './features/workspace.js';
const root=document.querySelector('#app');
let epoch=0;
const button=(name,fn)=>{const b=el('button',name);b.onclick=fn;return b;};
function lost({workspaceId}){if(workspaceId===null)return;epoch++;document.querySelectorAll('dialog').forEach(d=>d.close());root.replaceChildren(el('p','Access changed. Refresh your account to continue.'),button('Refresh account',refresh));}
const client=createClient({onAccessLost:lost});
function error(e){if(e.code==='context_changed')return;if(e.code==='authentication_required')login();else root.replaceChildren(el('p',e.message,{role:'alert'}),button('Refresh account',refresh));}
function login(){
 root.replaceChildren(el('h1','Sign in to Workpal'));const form=el('form',undefined,{method:'POST'});
 const user=el('input',undefined,{name:'username',autocomplete:'username',required:''});const pass=el('input',undefined,{name:'password',type:'password',autocomplete:'current-password',required:''});
 for(const [name,input] of [['Username',user],['Password',pass]]){const label=el('label',name);label.append(input);form.append(label);}
 const submit=el('button','Sign in',{type:'submit'}),msg=el('p',undefined,{role:'alert'});form.append(submit,msg);root.append(form);
 form.onsubmit=async e=>{e.preventDefault();submit.disabled=true;try{account(await client.login(user.value,pass.value));}catch(e){msg.textContent=e.message;}finally{pass.value='';submit.disabled=false;}};
}
function account(session){
 ++epoch;root.replaceChildren();const nav=el('nav');nav.append(el('span',session.user.username));
 const select=el('select',undefined,{'aria-label':'Workspace'});select.append(el('option','Select a workspace',{value:''}));
 session.workspaces.forEach(w=>select.append(el('option',`${w.name} (#${w.id})`,{value:w.id})));nav.append(select,button('Sign out',async()=>{epoch++;document.querySelectorAll('dialog').forEach(d=>d.close());root.replaceChildren(el('p','Signing out…',{role:'status'}));try{await client.logout();login();}catch{root.replaceChildren(el('p','Sign out has not been confirmed.',{role:'alert'}),button('Refresh account',refresh));}}));
 const content=el('section');root.append(nav,content);if(!session.workspaces.length)content.append(el('p','No workspaces are available.'));
 const pages=el('nav');root.insertBefore(pages,content);let page='Workspace';
 const close=()=>document.querySelectorAll('dialog').forEach(d=>d.close());
 const navigate=()=>{close();const token=++epoch;const args={client,content,current:()=>token===epoch,onError:error};if(page==='Issues')showIssues(args).catch(e=>{if(token===epoch)error(e);});else if(page==='Projects')showProjects(args).catch(e=>{if(token===epoch)error(e);});else showWorkspace({...args,onChange:fact=>{const option=[...select.options].find(o=>o.value===String(fact.id));if(option)option.textContent=`${fact.name} (#${fact.id})`;}});};
 for(const title of ['Workspace','Projects','Issues'])pages.append(button(title,()=>{page=title;navigate();}));pages.hidden=true;
 select.onchange=()=>{close();if(!select.value){epoch++;pages.hidden=true;content.replaceChildren();return;}client.selectWorkspace(Number(select.value));pages.hidden=false;page='Workspace';navigate();};
}
async function refresh(){root.replaceChildren(el('p','Loading account…',{role:'status'}));try{account(await client.loadSession());}catch(e){error(e);}}
refresh();
