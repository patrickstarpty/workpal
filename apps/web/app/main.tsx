import './storage-migration';
import {installLocalLinkNavigation} from './local-link-navigation';
import {ThemeProvider} from 'next-themes';
import {Toaster} from '@workpal/ui/components/ui/sonner';
import {LocalPage} from './routes';
import {PythonSession} from './python-session';
import {entryPath} from './entry-route';
import {CapabilityHub} from './capabilities/capability-hub';
import {capabilityView} from './capabilities/routes';
import React,{useState,useEffect} from 'react';
import {createRoot} from 'react-dom/client';
import {CoreProvider} from '../../../packages/core/platform';
import {WorkspaceSlugProvider} from '../../../packages/core/paths';
import {NavigationProvider} from '../../../packages/views/navigation';
import {SearchCommand} from '@workpal/views/search';
import {FloatingChat} from '@workpal/views/chat/floating-chat';
import {DashboardLayout} from '../../../packages/views/layout/dashboard-layout';
import {AppearanceSync} from '@workpal/views/common/appearance-sync';
import resources from '../../../packages/views/locales/en';
import './full-style.css';
class Boundary extends React.Component<React.PropsWithChildren,{error:boolean}> {
  state={error:false};
  static getDerivedStateFromError(){return {error:true};}
  componentDidCatch(error:Error){console.error(error);}
  render(){return this.state.error?<section role="alert" data-page-error className="m-auto p-8 text-center"><h1>Unable to display this page</h1><button className="mt-4 underline" onClick={()=>this.setState({error:false})}>Try again</button></section>:this.props.children;}
}
function App() {
  useEffect(()=>installLocalLinkNavigation(window),[]);
  const [path,setPath]=useState(()=>entryPath(location.hash));
  useEffect(()=>{
    const update=()=>setPath(entryPath(location.hash));
    window.addEventListener('hashchange',update);
    window.addEventListener('popstate',update);
    return()=>{window.removeEventListener('hashchange',update);window.removeEventListener('popstate',update);};
  },[]);
  useEffect(()=>{
    if(location.hash!=='#'+path && entryPath(location.hash)===path)history.replaceState(null,'','#'+path);
  },[path]);
  const url=new URL(path,location.origin);
  const capability=capabilityView(url.pathname);
  useEffect(()=>{document.title=url.pathname==='/login'?'Sign in · Workpal':capability?`${{overview:'Overview',skills:'Skill Hub',team:'Agent Team'}[capability]} · Workpal`:'Workpal';},[capability,url.pathname]);
  const nav={
    pathname:url.pathname,searchParams:url.searchParams,hash:url.hash,
    push:(next:string)=>{location.hash=next;setPath(next);},
    replace:(next:string)=>{history.replaceState(null,'','#'+next);setPath(next);},
    back:()=>history.back(),forward:()=>history.forward(),
    getShareableUrl:(next:string)=>`${location.origin}/#${next}`,
    openInNewTab:(next:string)=>{window.open(`${location.origin}/#${next}`,"_blank","noopener,noreferrer");},
  };
  return <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
    <CoreProvider localeAdapter={{getUserChoice:()=>"en",getSystemPreferences:()=>["en"],persist:()=>{}}} locale="en" resources={{en:resources}} cookieAuth wsUrl={`${location.protocol==='https:'?'wss:':'ws:'}//${location.host}/ws`} apiBaseUrl={location.origin} syncUserLocale={false}>
      <AppearanceSync/>
      <PythonSession requireEntry pathname={url.pathname} route={path} navigate={nav.replace} landing={<NavigationProvider value={nav}><CapabilityHub view={capability ?? 'overview'} navigate={nav.push} enterWorkspace={()=>nav.push('/workspaces')}/></NavigationProvider>}>
        {slug=><WorkspaceSlugProvider slug={slug}><NavigationProvider value={nav}>
        <DashboardLayout syncAppearance={false} bottomBarStart={<a className="workspace-ai-hub" href="#/home">AI Hub</a>} extra={<><SearchCommand/><FloatingChat/></>}>
          <Boundary key={url.pathname}><LocalPage pathname={url.pathname} workspaceSlug={slug}/></Boundary>
        </DashboardLayout>
        <Toaster/>
      </NavigationProvider></WorkspaceSlugProvider>}</PythonSession>
    </CoreProvider>
  </ThemeProvider>;
}
createRoot(document.getElementById('root')!).render(<Boundary><App/></Boundary>);
