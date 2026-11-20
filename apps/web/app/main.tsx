import React,{useState,useEffect,useRef} from 'react';
import {createRoot} from 'react-dom/client';
import {CoreProvider,setCurrentWorkspace} from '../../../packages/core/platform';
import {useQueryClient} from '@tanstack/react-query';
import {WorkspaceSlugProvider} from '../../../packages/core/paths';
import {useAuthStore} from '../../../packages/core/auth';
import {NavigationProvider} from '../../../packages/views/navigation';
import {DashboardLayout} from '../../../packages/views/layout/dashboard-layout';
import {ProjectsPage} from '../../../packages/views/projects/components/projects-page';
import {AgentsPage} from '../../../packages/views/agents/components/agents-page';
import SkillsPage from '../../../packages/views/skills/components/skills-page';
import {IssuesPage} from '../../../packages/views/issues/components/issues-page';
import {SquadsPage} from '../../../packages/views/squads/components';
import {AutopilotsPage} from '../../../packages/views/autopilots/components';
import {InboxPage} from '../../../packages/views/inbox';
import {ChatPage} from '../../../packages/views/chat';
import {SettingsPage} from '../../../packages/views/settings';
import {DashboardPage} from '../../../packages/views/dashboard';
import {ProjectDetail} from '../../../packages/views/projects/components/project-detail';
import {IssueDetailRoute} from '../../../packages/views/issues/components/issue-detail-route';
import {AgentDetailPage} from '../../../packages/views/agents/components/agent-detail-page';
import resources from '../../../packages/views/locales/en';
import './full-style.css';
const {workspace:ws,user,projects} = await fetch('/api/bootstrap').then(r=>{if(!r.ok)throw Error('Unable to load workspace');return r.json()});
class Boundary extends React.Component<any,{error:string}>{state={error:''};static getDerivedStateFromError(error:any){return {error:error.stack||error.message}}render(){return this.state.error?<pre id="reference-error">{this.state.error}</pre>:this.props.children}}
function Seed({children}:any){const qc=useQueryClient(),seeded=useRef(false);if(!seeded.current){seeded.current=true;qc.setQueryData(['workspaces','list'],[ws]);qc.setQueryData(['projects',ws.id,'list'],{projects,total:projects.length});useAuthStore.setState({user,status:'authenticated',isLoading:false});setCurrentWorkspace(ws.slug,ws.id);}return children;}
function App(){const [path,setPath]=useState(location.hash.slice(1)||'/review/projects');useEffect(()=>{const fn=()=>setPath(location.hash.slice(1)||'/review/projects');window.addEventListener('hashchange',fn);return()=>window.removeEventListener('hashchange',fn)},[]);const nav={pathname:path.split('?')[0],searchParams:new URLSearchParams(path.split('?')[1]||''),hash:'',push:(p:string)=>location.hash=p,replace:(p:string)=>location.hash=p,back:()=>history.back(),getShareableUrl:(p:string)=>p};const segments=path.split('?')[0].split('/').filter(Boolean);const detail=segments[2]?decodeURIComponent(segments[2]):null;const page=detail&&segments[1]==='projects'?<ProjectDetail projectId={detail}/>:detail&&segments[1]==='issues'?<IssueDetailRoute routeId={detail}/>:detail&&segments[1]==='agents'?<AgentDetailPage agentId={detail}/>:path.includes('/squads')?<SquadsPage/>:path.includes('/autopilots')?<AutopilotsPage/>:path.includes('/inbox')?<InboxPage/>:path.includes('/chat')?<ChatPage/>:path.includes('/settings')?<SettingsPage/>:path.includes('/dashboard')?<DashboardPage/>:path.includes('/agents')?<AgentsPage/>:path.includes('/skills')?<SkillsPage/>:path.includes('/issues')?<IssuesPage/>:<ProjectsPage/>;return <CoreProvider localeAdapter={{getUserChoice:()=>"en",getSystemPreferences:()=>["en"],persist:()=>{}}} locale="en" resources={{en:resources}} cookieAuth wsUrl="" apiBaseUrl={location.origin} syncUserLocale={false}><Seed><WorkspaceSlugProvider slug="review"><NavigationProvider value={nav}><DashboardLayout>{page}</DashboardLayout></NavigationProvider></WorkspaceSlugProvider></Seed></CoreProvider>}
createRoot(document.getElementById('root')!).render(<Boundary><App/></Boundary>);
