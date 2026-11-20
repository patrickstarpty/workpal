export class ClientError extends Error {
  constructor(code, message, {status=0,requestId=null,retryable=false,outcome='failed'}={}) {
    super(message); Object.assign(this,{name:'ClientError',code,status,requestId,retryable,outcome});
  }
}
function snapshot(value, seen=new Set(), schemaNumbers=false) {
  if(value===null || typeof value==='string' || typeof value==='boolean') return value;
  if(typeof value==='number' && Number.isFinite(value) && (schemaNumbers||!Number.isInteger(value)||Number.isSafeInteger(value))) return value;
  if(typeof value!=='object' || seen.has(value) || (!Array.isArray(value)&&Object.getPrototypeOf(value)!==Object.prototype)) throw new ClientError('invalid_input','Expected safe JSON.');
  seen.add(value);
  const result=Array.isArray(value)?Array.from(value,v=>snapshot(v,seen,schemaNumbers)):Object.fromEntries(Object.entries(value).map(([k,v])=>[k,snapshot(v,seen,schemaNumbers)]));
  seen.delete(value); return result;
}
const object=v=>v!==null && typeof v==='object' && !Array.isArray(v);
const positive=v=>Number.isSafeInteger(v)&&v>0;
const fields=(v,keys)=>object(v)&&Object.keys(v).length===keys.length&&keys.every(k=>Object.hasOwn(v,k));
const role=v=>['owner','admin','member'].includes(v);
const invalid=()=>new ClientError('invalid_response','Invalid response.',{outcome:'unknown'});
function validated(value, check, schemaNumbers=false) {
 try { const copy=snapshot(value,new Set(),schemaNumbers); if(!check(copy))throw invalid(); return copy; }
 catch { throw invalid(); }
}
function sessionValid(d) {
 return fields(d,['user','workspaces'])&&fields(d.user,['id','username'])&&positive(d.user.id)&&typeof d.user.username==='string'&&Array.isArray(d.workspaces)&&
 d.workspaces.every(w=>fields(w,['id','name','revision','role'])&&positive(w.id)&&positive(w.revision)&&typeof w.name==='string'&&role(w.role))&&new Set(d.workspaces.map(w=>w.id)).size===d.workspaces.length;
}
function actionValid(d) {
 return fields(d,['state','object_refs','data','error'])&&['completed','accepted','waiting_input','waiting_confirmation','waiting_user_auth','failed','unknown'].includes(d.state)&&Array.isArray(d.object_refs)&&d.object_refs.every(r=>fields(r,['kind','id'])&&typeof r.kind==='string'&&typeof r.id==='string')&&object(d.data);
}
function catalogValid(d) {
 return object(d)&&Array.isArray(d.actions)&&d.actions.every(a=>object(a)&&typeof a.action_id==='string'&&a.action_id.length>0&&object(a.schema)&&object(a.output_schema)&&['read','write','publish'].includes(a.capability)&&Array.isArray(a.allowed_roles)&&a.allowed_roles.every(role)&&typeof a.authorization==='string'&&['mutating','idempotency_required','confirmation_required','revision_required'].every(k=>typeof a[k]==='boolean')&&Object.hasOwn(a,'compensation'));
}
export function createClient({fetchImpl=globalThis.fetch,onAccessLost=()=>{}}={}) {
 let session=null,workspace=null,csrf=null,generation=0,authTail=Promise.resolve();
 const stale=()=>new ClientError('context_changed','Context changed.',{outcome:'unknown'});
 async function request(path,body,g=generation,schemaNumbers=false,current=()=>true) {
  const obsolete=()=>g!==generation||current()!==true;
  if(obsolete()) throw stale();
  let response,data;
  try {
   response=await fetchImpl('/api/v1/'+path,{method:body===undefined?'GET':'POST',credentials:'same-origin',mode:'same-origin',cache:'no-store',redirect:'error',headers:body===undefined?{}:{'Content-Type':'application/json','X-CSRFToken':csrf},...(body===undefined?{}:{body:JSON.stringify(body)})});
  } catch { if(obsolete()) throw stale(); throw new ClientError('transport_error','Request outcome is unknown.',{outcome:'unknown',retryable:true}); }
  if(obsolete()) {
   // The caller no longer owns this response. Release its unread stream so a
   // late large result cannot leave the connection receiving in the background.
   try { void response.body?.cancel().catch(()=>{}); } catch {}
   throw stale();
  }
  try { data=validated(await response.json(),object,schemaNumbers); }
  catch { if(obsolete())throw stale(); if(response.status===403||response.status===404)onAccessLost({workspaceId:workspace?.id??null,code:'invalid_response'}); throw invalid(); }
  if(obsolete()) throw stale();
  if(!response.ok) {
   const e=data.error||data;
   if(!object(e)||typeof e.code!=='string'||typeof e.message!=='string') {
    if(response.status===403||response.status===404)onAccessLost({workspaceId:workspace?.id??null,code:'invalid_response'});
    throw invalid();
   }
   if(response.status===403||response.status===404) {
    const workspaceId=workspace?.id??null;
    if(e.code==='authentication_required'){session=null;workspace=null;csrf=null;generation++;}
    onAccessLost({workspaceId,code:e.code});
   }
   throw new ClientError(e.code||'request_failed',e.message||'Request failed.',{status:response.status,requestId:e.request_id??null,retryable:e.retryable===true});
  }
  return snapshot(data,new Set(),schemaNumbers);
 }
 async function token(g){const d=await request('auth/csrf',undefined,g);if(typeof d.csrf_token!=='string'||!d.csrf_token)throw new ClientError('invalid_response','Missing CSRF token.',{outcome:'unknown'});csrf=d.csrf_token;}
 async function readSession(g=generation){
  const d=await request('auth/session',undefined,g);
  validated(d,sessionValid);
  if(JSON.stringify(session)!==JSON.stringify(d))generation++;
  session=snapshot(d); workspace=workspace?session.workspaces.find(w=>w.id===workspace.id)||null:null;
  return snapshot(session);
 }
 function selected(){if(!workspace)throw new ClientError('workspace_required','Select a workspace.');return workspace.id;}
 function authenticate(run) {
  generation++;session=null;workspace=null;csrf=null;
  const g=generation;
  const pending=authTail.then(async()=>{if(g!==generation)throw stale();await token(g);return run(g);});
  authTail=pending.catch(()=>{});return pending;
 }
 async function loadSession(){
  // A newer authentication intent may join while this refresh is waiting.
  let barrier;
  do { barrier=authTail;await barrier; } while(barrier!==authTail);
  return readSession();
 }
 return {
  loadSession,
  login(username,password){const body=snapshot({username,password});return authenticate(async g=>{validated(await request('auth/login',body,g),d=>fields(d,['user_id'])&&positive(d.user_id));await token(g);return readSession(g);});},
  logout(){return authenticate(async g=>{try{return validated(await request('auth/logout',{},g),d=>fields(d,['state'])&&d.state==='completed');}finally{if(g===generation){generation++;session=null;workspace=null;csrf=null;}}});},
  selectWorkspace(id){const w=session?.workspaces.find(w=>w.id===id);if(!w)throw new ClientError('workspace_required','Unknown workspace.');if(workspace?.id!==id)generation++;workspace=w;return snapshot(w);},
  async catalog(){
   // Schema bounds describe server integers; they are not executable client
   // constraints. Business values and IDs still require safe JS integers.
   return validated(await request('actions?workspace_id='+encodeURIComponent(selected()),undefined,generation,true),catalogValid,true);
  },
  async perform(actionId,payload,{revision,key,confirmationId,current=()=>true}={}){
   if(typeof current!=='function')throw new ClientError('invalid_input','Invalid request context.');
   if(current()!==true)throw stale();
   const body=snapshot({workspace_id:selected(),payload,...(revision===undefined?{}:{expected_revision:revision}),...(key===undefined?{}:{idempotency_key:key}),...(confirmationId===undefined?{}:{confirmation_id:confirmationId})});
   if(typeof actionId!=='string'||!actionId||actionId==='.'||actionId==='..')throw new ClientError('invalid_input','Invalid action.');
   const g=generation;if(!csrf)await token(g);return validated(await request('actions/'+encodeURIComponent(actionId),body,g,false,current),actionValid);
  }
 };
}
