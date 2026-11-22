import {useEffect,useRef,useState,type ReactNode} from 'react';
import {useQuery,useQueryClient} from '@tanstack/react-query';
import {useAuthStore} from '../../../packages/core/auth';
import {api} from '../../../packages/core/api';
import {setCurrentWorkspace} from '../../../packages/core/platform';
import {workspaceListOptions,workspaceKeys} from '../../../packages/core/workspace/queries';
import {VerificationLogin} from './verification-login';
import {capabilityView} from './capabilities/routes';
import {useAgentsViewStore, EMPTY_AGENT_FILTERS} from '../../../packages/core/agents/stores';
import {useSquadsViewStore, EMPTY_SQUAD_FILTERS} from '../../../packages/core/squads/stores';
import {loginDestination} from './entry-route';
export function resolveWorkspaceSlug(path:string,slugs:string[]){try{const slug=decodeURIComponent(path.split('/').filter(Boolean)[0]||'');return slugs.includes(slug)?slug:null;}catch{return null;}}
export function PythonSession({pathname,route=pathname,navigate,children,landing,requireEntry=false}:{pathname:string;route?:string;requireEntry?:boolean;navigate:(path:string)=>void;children:(slug:string)=>ReactNode;landing?:ReactNode}){
 const [entered,setEntered]=useState(!requireEntry);
 const status=useAuthStore(s=>s.status);
 const expired=useAuthStore(s=>s.expired);
 const previousStatus=useRef(status);
 const isLogin=pathname==='/login';
 useEffect(()=>{
  if(!entered){if(!isLogin)navigate('/login');return;}
  const loggedOut=previousStatus.current==='authenticated'&&status==='unauthenticated'&&!expired;
  previousStatus.current=status;
  if(status==='unauthenticated'&&!isLogin)navigate(loggedOut||route==='/home'||route==='/'?'/login':'/login?next='+encodeURIComponent(route));
  if(status==='authenticated'&&isLogin)navigate(loginDestination(route));
 },[status,expired,isLogin,route,navigate,entered]);
 if(!entered || status==='unauthenticated')return <VerificationLogin onSignedIn={()=>setEntered(true)}/>;
 if(status==='recovering')return <section role="alert" className="m-auto p-6">Unable to reach Workpal. <button onClick={()=>useAuthStore.getState().retryAuthentication()}>Try again</button></section>;
 if(status!=='authenticated')return <p role="status" className="m-auto p-6">Connecting to Workpal…</p>;
 if(isLogin)return <p role="status" className="m-auto p-6">Opening Workpal…</p>;
 if(landing && capabilityView(pathname))return landing;
 return <WorkspaceSession showAll={requireEntry} pathname={pathname} navigate={navigate}>{children}</WorkspaceSession>;
}
function WorkspaceSession({pathname,navigate,children,showAll=false}:{showAll?:boolean;pathname:string;navigate:(path:string)=>void;children:(slug:string)=>ReactNode}){
 const userId=useAuthStore(state=>state.user?.id);
 const preferenceKey=userId ? `workpal:last-workspace:${userId}` : null;
 const qc=useQueryClient();
 const query=useQuery({...workspaceListOptions(),retry:false,refetchOnWindowFocus:'always',staleTime:0});
 const [ready,setReady]=useState<string|null>(null),[name,setName]=useState(''),[slug,setSlug]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 const selected=resolveWorkspaceSlug(pathname,(query.data??[]).map(w=>w.slug));
 const workspace=query.data?.find(w=>w.slug===selected);
 useEffect(()=>{
  if(!preferenceKey || !workspace || ready!==workspace.slug || query.isError)return;
  try{localStorage.setItem(preferenceKey,workspace.id);}catch{/* Storage may be unavailable; navigation still works. */}
 },[preferenceKey,workspace?.id,workspace?.slug,ready,query.isError]);
 useEffect(()=>{setReady(null);if(!workspace||query.isError){setCurrentWorkspace(null,null);return;}let active=true;void qc.cancelQueries({predicate:q=>!['config','auth','me'].includes(String(q.queryKey[0])) && !(q.queryKey[0]==='workspaces' && q.queryKey[1]==='list')}).then(async()=>{if(!active)return;qc.removeQueries({predicate:q=>!['config','auth','me'].includes(String(q.queryKey[0])) && !(q.queryKey[0]==='workspaces' && q.queryKey[1]==='list')});setCurrentWorkspace(workspace.slug,workspace.id);await Promise.resolve();if(!active)return;if(showAll){useAgentsViewStore.setState({scope:"all",search:"",sortField:"name",sortDirection:"asc",filters:EMPTY_AGENT_FILTERS});useSquadsViewStore.setState({scope:"all",filters:EMPTY_SQUAD_FILTERS});}setReady(workspace.slug);});return()=>{active=false;setCurrentWorkspace(null,null);};},[workspace?.id,workspace?.slug,qc,query.isError,showAll]);
 useEffect(()=>{
  if(query.isError || !['/','/landing','/welcome','/login','/workspaces'].includes(pathname))return;
  // SMART's stable slug survives display-name changes. Only select accessible memberships.
  let previous:string|null=null;
  try{previous=preferenceKey ? localStorage.getItem(preferenceKey) : null;}catch{/* Use the default when storage is unavailable. */}
  const preferred=query.data?.find(workspace=>workspace.id===previous) ?? query.data?.find(workspace=>workspace.slug==='workpal-team') ?? (query.data?.length===1?query.data[0]:undefined);
  if(preferred)navigate('/'+encodeURIComponent(preferred.slug)+'/issues');
 },[query.data,query.isError,pathname,navigate,preferenceKey]);
 if(query.isError)return <section role="alert" className="m-auto p-6">Unable to load workspaces. <button onClick={()=>void query.refetch()}>Try again</button></section>;
 if(query.isPending)return <p role="status">Loading workspaces…</p>;
 if(workspace&&ready!==workspace.slug)return <p role="status">Resolving workspace…</p>;
 if(workspace&&ready===workspace.slug)return <div key={workspace.id} className="workspace-session flex h-svh flex-col overflow-hidden"><div className="workspace-session-content flex min-h-0 flex-1 flex-col">{children(workspace.slug)}</div></div>;
 return <main className="m-auto w-full max-w-md space-y-4 p-6"><a className="text-label underline" href="#/home">Back to capabilities</a><h1 className="text-xl font-semibold">Choose a workspace</h1>{!['/','/landing','/welcome','/login','/workspaces'].includes(pathname)&&<p role="alert">This workspace is unavailable or you do not have access.</p>}{query.data.map(w=><button className="block underline" key={w.id} onClick={()=>navigate('/'+encodeURIComponent(w.slug)+'/issues')}>{w.name}</button>)}<form className="flex flex-col gap-3" onSubmit={async e=>{e.preventDefault();setBusy(true);setError('');try{const w=await api.createWorkspace({name,slug});await qc.invalidateQueries({queryKey:workspaceKeys.list()});navigate('/'+encodeURIComponent(w.slug)+'/issues');}catch{setError('Unable to create workspace. Try again.');}finally{setBusy(false);}}}><h2>Create a workspace</h2><label>Name<input className="w-full border p-2" required value={name} onChange={e=>setName(e.target.value)}/></label><label>Workspace URL<input className="w-full border p-2" required value={slug} onChange={e=>setSlug(e.target.value)}/></label>{error&&<p role="alert">{error}</p>}<button disabled={busy}>Create workspace</button></form></main>;
}
