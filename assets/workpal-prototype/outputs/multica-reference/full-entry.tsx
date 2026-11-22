import React,{useState,useEffect,useRef} from 'react';
import {createRoot} from 'react-dom/client';
import {CoreProvider,setCurrentWorkspace} from '../../../multica/packages/core/platform';
import {useQueryClient} from '@tanstack/react-query';
import {WorkspaceSlugProvider} from '../../../multica/packages/core/paths';
import {useAuthStore} from '../../../multica/packages/core/auth';
import {NavigationProvider} from '../../../multica/packages/views/navigation';
import {DashboardLayout} from '../../../multica/packages/views/layout/dashboard-layout';
import {ProjectsPage} from '../../../multica/packages/views/projects/components/projects-page';
import {AgentsPage} from '../../../multica/packages/views/agents/components/agents-page';
import SkillsPage from '../../../multica/packages/views/skills/components/skills-page';
import {IssuesPage} from '../../../multica/packages/views/issues/components/issues-page';
import {SquadsPage} from '../../../multica/packages/views/squads/components';
import {AutopilotsPage} from '../../../multica/packages/views/autopilots/components';
import {InboxPage} from '../../../multica/packages/views/inbox';
import {ChatPage} from '../../../multica/packages/views/chat';
import {SettingsPage} from '../../../multica/packages/views/settings';
import {DashboardPage} from '../../../multica/packages/views/dashboard';
import resources from '../../../multica/packages/views/locales/en';
import './full-style.css';
import {ws,user,projects,installDataAdapter} from './data-adapter';
installDataAdapter();
class Boundary extends React.Component<any,{error:string}>{state={error:''};static getDerivedStateFromError(error:any){return {error:error.stack||error.message}}render(){return this.state.error?<pre id="reference-error">{this.state.error}</pre>:this.props.children}}
function Seed({children}:any){const qc=useQueryClient(),seeded=useRef(false);if(!seeded.current){seeded.current=true;qc.setQueryData(['workspaces','list'],[ws]);qc.setQueryData(['projects',ws.id,'list'],{projects,total:projects.length});useAuthStore.setState({user,status:'authenticated',isLoading:false});setCurrentWorkspace(ws.slug,ws.id);}return children;}
function App(){const [path,setPath]=useState(location.hash.slice(1)||'/review/projects');useEffect(()=>{const fn=()=>setPath(location.hash.slice(1)||'/review/projects');window.addEventListener('hashchange',fn);return()=>window.removeEventListener('hashchange',fn)},[]);const nav={pathname:path.split('?')[0],searchParams:new URLSearchParams(path.split('?')[1]||''),hash:'',push:(p:string)=>location.hash=p,replace:(p:string)=>location.hash=p,back:()=>history.back(),getShareableUrl:(p:string)=>p};const page=path.includes('/squads')?<SquadsPage/>:path.includes('/autopilots')?<AutopilotsPage/>:path.includes('/inbox')?<InboxPage/>:path.includes('/chat')?<ChatPage/>:path.includes('/settings')?<SettingsPage/>:path.includes('/dashboard')?<DashboardPage/>:path.includes('/agents')?<AgentsPage/>:path.includes('/skills')?<SkillsPage/>:path.includes('/issues')?<IssuesPage/>:<ProjectsPage/>;return <CoreProvider localeAdapter={{getUserChoice:()=>"en",getSystemPreferences:()=>["en"],persist:()=>{}}} locale="en" resources={{en:resources}} cookieAuth apiBaseUrl="https://reference.invalid" syncUserLocale={false}><Seed><WorkspaceSlugProvider slug="review"><NavigationProvider value={nav}><DashboardLayout>{page}</DashboardLayout></NavigationProvider></WorkspaceSlugProvider></Seed></CoreProvider>}
createRoot(document.getElementById('root')!).render(<Boundary><App/></Boundary>);
