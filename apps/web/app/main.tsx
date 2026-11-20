import {ThemeProvider} from 'next-themes';
import {Toaster} from '@workpal/ui/components/ui/sonner';
import {LocalPage} from './routes';
import './storage-migration';
import React,{useState,useEffect,useRef} from 'react';
import {createRoot} from 'react-dom/client';
import {CoreProvider,setCurrentWorkspace} from '../../../packages/core/platform';
import {useQueryClient} from '@tanstack/react-query';
import {WorkspaceSlugProvider} from '../../../packages/core/paths';
import {useAuthStore} from '../../../packages/core/auth';
import {NavigationProvider} from '../../../packages/views/navigation';
import {SearchCommand} from '@workpal/views/search';
import {FloatingChat} from '@workpal/views/chat/floating-chat';
import {DashboardLayout} from '../../../packages/views/layout/dashboard-layout';
import resources from '../../../packages/views/locales/en';
import './full-style.css';
const {workspace:ws,user,projects} = await fetch('/api/bootstrap').then(r=>{if(!r.ok)throw Error('Unable to load workspace');return r.json()});
class Boundary extends React.Component<React.PropsWithChildren,{error:boolean}> {
  state={error:false};
  static getDerivedStateFromError(){return {error:true};}
  componentDidCatch(error:Error){console.error(error);}
  render(){return this.state.error?<section role="alert" data-page-error className="m-auto p-8 text-center"><h1>Unable to display this page</h1><button className="mt-4 underline" onClick={()=>this.setState({error:false})}>Try again</button></section>:this.props.children;}
}
function Seed({children}:any){const qc=useQueryClient(),seeded=useRef(false);if(!seeded.current){seeded.current=true;qc.setQueryData(['workspaces','list'],[ws]);qc.setQueryData(['projects',ws.id,'list'],{projects,total:projects.length});useAuthStore.setState({user,status:'authenticated',isLoading:false});setCurrentWorkspace(ws.slug,ws.id);}return children;}
function App() {
  const [path,setPath]=useState(location.hash.slice(1)||'/review/projects');
  useEffect(()=>{
    const update=()=>setPath(location.hash.slice(1)||'/review/projects');
    window.addEventListener('hashchange',update);
    window.addEventListener('popstate',update);
    return()=>{window.removeEventListener('hashchange',update);window.removeEventListener('popstate',update);};
  },[]);
  const url=new URL(path,location.origin);
  const nav={
    pathname:url.pathname,searchParams:url.searchParams,hash:url.hash,
    push:(next:string)=>{location.hash=next;},
    replace:(next:string)=>{history.replaceState(null,'','#'+next);setPath(next);},
    back:()=>history.back(),forward:()=>history.forward(),
    getShareableUrl:(next:string)=>`${location.origin}/#${next}`,
    openInNewTab:(next:string)=>{window.open(`${location.origin}/#${next}`,"_blank","noopener,noreferrer");},
  };
  return <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
    <CoreProvider localeAdapter={{getUserChoice:()=>"en",getSystemPreferences:()=>["en"],persist:()=>{}}} locale="en" resources={{en:resources}} cookieAuth wsUrl="" apiBaseUrl={location.origin} syncUserLocale={false}>
      <Seed><WorkspaceSlugProvider slug="review"><NavigationProvider value={nav}>
        <DashboardLayout extra={<><SearchCommand/><FloatingChat/></>}>
          <Boundary key={url.pathname}><LocalPage pathname={url.pathname}/></Boundary>
        </DashboardLayout>
        <Toaster/>
      </NavigationProvider></WorkspaceSlugProvider></Seed>
    </CoreProvider>
  </ThemeProvider>;
}
createRoot(document.getElementById('root')!).render(<Boundary><App/></Boundary>);
