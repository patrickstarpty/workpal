import {render,screen,fireEvent,waitFor} from '@testing-library/react';
import {vi,it,expect,afterEach} from 'vitest';
import {VerificationLogin} from './verification-login';
const retry=vi.hoisted(()=>vi.fn());
const verify=vi.hoisted(()=>vi.fn().mockResolvedValue({}));
vi.mock('../../../packages/core/auth',()=>({useAuthStore: Object.assign((select:any)=>select(state),{getState:()=>({verifyCode:verify,retryAuthentication:retry})})}));
afterEach(()=>{vi.unstubAllGlobals();vi.clearAllMocks();state.status='authenticated';state.expired=false;localStorage.clear();});
it('prefills only with server capability and waits for editable manual submission',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response(JSON.stringify({development_auth:true}))));
 render(<VerificationLogin/>);
 const email=await screen.findByDisplayValue('workpal@fwd.com');
 expect(screen.getAllByRole('textbox')).toHaveLength(1);
 expect(screen.queryByLabelText('Verification code')).toBeNull();
 expect(verify).not.toHaveBeenCalled();
 fireEvent.change(email,{target:{value:'edited@example.com'}});
 fireEvent.click(screen.getByRole('button',{name:'Sign in'}));
 await waitFor(()=>expect(verify).toHaveBeenCalledWith('edited@example.com','888888'));
});
it('does not prefill without explicit capability',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response('{}')));
 render(<VerificationLogin/>);
 await waitFor(()=>expect(screen.getByLabelText('Email')).toHaveValue(''));
 await waitFor(()=>expect(screen.getByRole('button',{name:'Sign in'})).toBeDisabled());
 expect(verify).not.toHaveBeenCalled();
});
it('shows a failed verification without fabricating a session',async()=>{
 verify.mockRejectedValueOnce(Error('unauthorized'));
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response('{"development_auth":true}')));
 render(<VerificationLogin/>);
 await screen.findByDisplayValue('workpal@fwd.com');
 fireEvent.click(screen.getByRole('button',{name:'Sign in'}));
 expect(await screen.findByRole('alert')).toHaveTextContent('Unable to sign in');
});

import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {PythonSession} from './python-session';
const state=vi.hoisted(()=>({status:'authenticated',expired:false,user:{id:'user-1'}}));
const list=vi.hoisted(()=>vi.fn());
vi.mock('../../../packages/core/api',()=>({api:{listWorkspaces:list}}));
vi.mock('../../../packages/core/platform',()=>({setCurrentWorkspace:vi.fn()}));
// Exercise the boundary with the same selector contract as the core store.

for(const path of ['/missing/projects','/%ZZ/projects','/'])it('offers workspace selection for '+path,async()=>{
 state.status='authenticated';list.mockResolvedValue([]);
 render(<QueryClientProvider client={new QueryClient()}><PythonSession pathname={path} navigate={vi.fn()}>{()=> <p>Private content</p>}</PythonSession></QueryClientProvider>);
 expect(await screen.findByText('Choose a workspace')).toBeVisible();
 expect(screen.queryByText('Private content')).toBeNull();
});
it('preserves a non-review deep link after membership resolution',async()=>{
 list.mockResolvedValue([{id:'a',slug:'team',name:'Team'}]);const navigate=vi.fn();
 render(<QueryClientProvider client={new QueryClient()}><PythonSession pathname="/team/tasks/123" navigate={navigate}>{slug=><p>Private {slug}</p>}</PythonSession></QueryClientProvider>);
 expect(await screen.findByText('Private team')).toBeVisible();expect(navigate).not.toHaveBeenCalled();
});

import {setCurrentWorkspace} from '../../../packages/core/platform';
it('offers retry during recovery and removes private content after expiry',async()=>{
 const qc=new QueryClient();list.mockResolvedValue([{id:'a',slug:'team',name:'Team'}]);state.status='authenticated';
 const view=()=> <QueryClientProvider client={qc}><PythonSession pathname="/team/projects" navigate={vi.fn()}>{()=> <p>Private content</p>}</PythonSession></QueryClientProvider>;
 const rendered=render(view());await screen.findByText('Private content');
 state.status='recovering';rendered.rerender(view());
 expect(screen.queryByText('Private content')).toBeNull();
 fireEvent.click(screen.getByRole('button',{name:'Try again'}));expect(retry).toHaveBeenCalledOnce();
 expect(setCurrentWorkspace).toHaveBeenLastCalledWith(null,null);
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response('{}')));
 state.status='unauthenticated';rendered.rerender(view());
 expect(await screen.findByLabelText('Email')).toBeVisible();expect(screen.queryByText('Private content')).toBeNull();
 state.status='authenticated';
});
it('switches to the new workspace root after clearing old resource queries',async()=>{
 state.status='authenticated';const qc=new QueryClient();const navigate=vi.fn();
 list.mockResolvedValue([{id:'a',slug:'team',name:'Team'},{id:'b',slug:'other',name:'Other'}]);
 const view=(path:string)=><QueryClientProvider client={qc}><PythonSession pathname={path} navigate={navigate}>{slug=><p>Private {slug}</p>}</PythonSession></QueryClientProvider>;
 const rendered=render(view('/team/issues/old-resource'));await screen.findByText('Private team');
 qc.setQueryData(['issues','a','old-resource'],{private:true});qc.setQueryData(['config'],{development_auth:true});
 rendered.rerender(view('/other/projects'));await screen.findByText('Private other');
 expect(qc.getQueryData(['issues','a','old-resource'])).toBeUndefined();
 expect(qc.getQueryData(['config'])).toEqual({development_auth:true});
 expect(setCurrentWorkspace).toHaveBeenLastCalledWith('other','b');
});
it('requires selection for multiple memberships and selects a sole membership at entry',async()=>{
 state.status='authenticated';const navigate=vi.fn();list.mockResolvedValue([{id:'a',slug:'team',name:'Team'},{id:'b',slug:'other',name:'Other'}]);
 const first=render(<QueryClientProvider client={new QueryClient()}><PythonSession pathname="/" navigate={navigate}>{()=> <p>Private</p>}</PythonSession></QueryClientProvider>);
 await screen.findByText('Choose a workspace');expect(navigate).not.toHaveBeenCalled();first.unmount();
 list.mockResolvedValue([{id:'a',slug:'team',name:'Team'}]);
 render(<QueryClientProvider client={new QueryClient()}><PythonSession pathname="/" navigate={navigate}>{()=> <p>Private</p>}</PythonSession></QueryClientProvider>);
 await waitFor(()=>expect(navigate).toHaveBeenCalledWith('/team/issues'));
});


it('shows manual login on rejected authentication and never mounts private children',async()=>{
 state.status='unauthenticated';vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response('{}')));
 render(<PythonSession pathname="/team/projects" navigate={vi.fn()}>{()=> <p>Private content</p>}</PythonSession>);
 expect(screen.getByLabelText('Email')).toBeVisible();expect(screen.queryByText('Private content')).toBeNull();expect(list).not.toHaveBeenCalled();
});
it('offers core authentication retry for transport recovery',()=>{
 state.status='recovering';
 render(<PythonSession pathname="/team/projects" navigate={vi.fn()}>{()=> <p>Private content</p>}</PythonSession>);
 fireEvent.click(screen.getByRole('button',{name:'Try again'}));expect(retry).toHaveBeenCalledOnce();expect(list).not.toHaveBeenCalled();expect(screen.queryByText('Private content')).toBeNull();
});
it('redirects a single membership entry to issues',async()=>{
 list.mockResolvedValue([{id:'a',slug:'team',name:'Team'}]);const navigate=vi.fn();
 render(<QueryClientProvider client={new QueryClient()}><PythonSession pathname="/landing" navigate={navigate}>{()=> <p>Private content</p>}</PythonSession></QueryClientProvider>);
 await waitFor(()=>expect(navigate).toHaveBeenCalledWith('/team/issues'));expect(screen.queryByText('Private content')).toBeNull();
});
it('keeps an authenticated capability entry outside the workspace until the user enters',async()=>{
 list.mockResolvedValue([{id:'a',slug:'team',name:'Team'}]);const navigate=vi.fn();
 const client=new QueryClient();
 const view=(pathname:string)=><QueryClientProvider client={client}><PythonSession pathname={pathname} navigate={navigate} landing={<h1>AI capabilities</h1>}>{()=> <p>Private workspace content</p>}</PythonSession></QueryClientProvider>;
 const mounted=render(view('/home'));
 expect(screen.getByRole('heading',{name:'AI capabilities'})).toBeVisible();
 expect(navigate).not.toHaveBeenCalled();expect(list).not.toHaveBeenCalled();
 mounted.rerender(view('/workspaces'));
 await waitFor(()=>expect(navigate).toHaveBeenCalledWith('/team/issues'));
});
it('gates capability pages behind the existing sign-in boundary',async()=>{
 state.status='unauthenticated';vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response('{}')));
 render(<PythonSession pathname="/home/skills" navigate={vi.fn()} landing={<h1>AI capabilities</h1>}>{()=> <p>Private</p>}</PythonSession>);
 expect(screen.getByLabelText('Email')).toBeVisible();expect(screen.queryByText('AI capabilities')).toBeNull();
});
it('uses the login URL when an unauthenticated visitor opens home',async()=>{
 state.status='unauthenticated';vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response('{}')));
 const navigate=vi.fn();
 render(<PythonSession pathname="/home" navigate={navigate} landing={<h1>AI capabilities</h1>}>{()=> <p>Private</p>}</PythonSession>);
 await waitFor(()=>expect(navigate).toHaveBeenCalledWith('/login'));
 expect(screen.getByLabelText('Email')).toBeVisible();expect(screen.queryByText('AI capabilities')).toBeNull();
});
it('preserves the full protected destination in the login URL',async()=>{
 state.status='unauthenticated';state.expired=true;vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response('{}')));
 const navigate=vi.fn();const route='/team/issues/123?tab=activity#comment-4';
 render(<PythonSession pathname="/team/issues/123" route={route} navigate={navigate}>{()=> <p>Private</p>}</PythonSession>);
 await waitFor(()=>expect(navigate).toHaveBeenCalledWith('/login?next='+encodeURIComponent(route)));
 expect(screen.queryByText('Private')).toBeNull();
});
it('keeps an unauthenticated login URL without redirect loops',async()=>{
 state.status='unauthenticated';vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response('{}')));
 const navigate=vi.fn();
 render(<PythonSession pathname="/login" navigate={navigate}>{()=> <p>Private</p>}</PythonSession>);
 await screen.findByLabelText('Email');expect(navigate).not.toHaveBeenCalled();
});
for(const [route,destination] of [
 ['/login','/home'],
 ['/login?next=%2Fteam%2Fissues%2F123%3Ftab%3Dactivity%23comment-4','/team/issues/123?tab=activity#comment-4'],
 ['/login?next=https%3A%2F%2Fexample.com','/home'],
 ['/login?next=%2F%2Fexample.com','/home'],
 ['/login?next=%2Flogin%3Fnext%3D%2Fhome','/home'],
])it('leaves authenticated login '+route+' for '+destination,async()=>{
 state.status='authenticated';list.mockResolvedValue([{id:'a',slug:'team',name:'Team'}]);const navigate=vi.fn();
 render(<QueryClientProvider client={new QueryClient()}><PythonSession pathname="/login" route={route} navigate={navigate} landing={<h1>AI capabilities</h1>}>{()=> <p>Private</p>}</PythonSession></QueryClientProvider>);
 await waitFor(()=>expect(navigate).toHaveBeenCalledWith(destination));
 expect(list).not.toHaveBeenCalled();
});
it('offers multiple memberships without silently selecting one',async()=>{
 list.mockResolvedValue([{id:'a',slug:'team',name:'Team'},{id:'b',slug:'other',name:'Other'}]);const navigate=vi.fn();
 render(<QueryClientProvider client={new QueryClient()}><PythonSession pathname="/landing" navigate={navigate}>{()=> <p>Private content</p>}</PythonSession></QueryClientProvider>);
 fireEvent.click(await screen.findByRole('button',{name:'Other'}));expect(navigate).toHaveBeenCalledWith('/other/issues');
});
for(const expired of [false,true])it('unmounts private content on '+(expired?'expiry':'logout'),async()=>{
 list.mockResolvedValue([{id:'a',slug:'team',name:'Team'}]);vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response('{}')));
 const client=new QueryClient();const navigate=vi.fn();const view=()=> <QueryClientProvider client={client}><PythonSession pathname="/team/projects" navigate={navigate}>{()=> <p>Private content</p>}</PythonSession></QueryClientProvider>;
 const mounted=render(view());await screen.findByText('Private content');state.status='unauthenticated';state.expired=expired;mounted.rerender(view());
 expect(screen.queryByText('Private content')).toBeNull();expect(screen.getByLabelText('Email')).toBeVisible();
 expect(navigate).toHaveBeenLastCalledWith(expired?'/login?next=%2Fteam%2Fprojects':'/login');
});

it('switches resource routes to projects and clears private caches before rendering the new context',async()=>{
 const {setCurrentWorkspace}=await import('../../../packages/core/platform');
 list.mockResolvedValue([{id:'a',slug:'team',name:'Team'},{id:'b',slug:'other',name:'Other'}]);
 const client=new QueryClient();const navigate=vi.fn();
 const view=(path:string)=> <QueryClientProvider client={client}><PythonSession pathname={path} navigate={navigate}>{slug=>{
  if(slug==='other'){
   expect(client.getQueryData(['workspaces','a','members'])).toBeUndefined();
   expect(client.getQueryData(['issues','a'])).toBeUndefined();
  }
  return <p>Private {slug}</p>;
 }}</PythonSession></QueryClientProvider>;
 const mounted=render(view('/team/tasks/old-id'));await screen.findByText('Private team');
 client.setQueryData(['workspaces','a','members'],['secret']);client.setQueryData(['issues','a'],['secret']);
 client.setQueryData(['config'],{public:true});client.setQueryData(['auth'],{valid:true});
 mounted.rerender(view('/other/projects'));await screen.findByText('Private other');
 expect(setCurrentWorkspace).toHaveBeenLastCalledWith('other','b');
 expect(client.getQueryData(['config'])).toEqual({public:true});expect(client.getQueryData(['auth'])).toEqual({valid:true});
});
it('requires a fresh sign-in on each application mount even with a saved session',async()=>{
 vi.stubGlobal('fetch',vi.fn().mockResolvedValue(new Response('{"development_auth":true}')));
 state.status='authenticated';const navigate=vi.fn();
 render(<PythonSession requireEntry pathname="/home" navigate={navigate} landing={<p>Capabilities</p>}>{()=> <p>Private</p>}</PythonSession>);
 await screen.findByDisplayValue('workpal@fwd.com');
 expect(screen.queryByText('Capabilities')).toBeNull();
 expect(navigate).toHaveBeenCalledWith('/login');
 fireEvent.click(screen.getByRole('button',{name:'Sign in'}));
 await screen.findByText('Capabilities');
});

for(const path of ['/','/workspaces','/landing'])it('defaults to SMART from '+path+' when accessible',async()=>{
 list.mockResolvedValue([{id:'a',slug:'review',name:'TAP'},{id:'smart',slug:'workpal-team',name:'SMART'}]);const navigate=vi.fn();
 render(<QueryClientProvider client={new QueryClient()}><PythonSession pathname={path} navigate={navigate}>{()=> <p>Private</p>}</PythonSession></QueryClientProvider>);
 await waitFor(()=>expect(navigate).toHaveBeenCalledWith('/workpal-team/issues'));
});
it('preserves explicit TAP links even when SMART is the default',async()=>{
 list.mockResolvedValue([{id:'a',slug:'review',name:'TAP'},{id:'smart',slug:'workpal-team',name:'SMART'}]);const navigate=vi.fn();
 render(<QueryClientProvider client={new QueryClient()}><PythonSession pathname="/review/issues/existing" navigate={navigate}>{slug=><p>Private {slug}</p>}</PythonSession></QueryClientProvider>);
 expect(await screen.findByText('Private review')).toBeVisible();expect(navigate).not.toHaveBeenCalled();
});

it('remembers the last accessible workspace after remounting',async()=>{
 const memberships=[{id:'a',slug:'review',name:'TAP'},{id:'smart',slug:'workpal-team',name:'SMART'}];
 list.mockResolvedValue(memberships);const navigate=vi.fn();
 const first=render(<QueryClientProvider client={new QueryClient()}><PythonSession pathname="/review/issues/existing" navigate={navigate}>{slug=><p>Private {slug}</p>}</PythonSession></QueryClientProvider>);
 await screen.findByText('Private review');first.unmount();
 render(<QueryClientProvider client={new QueryClient()}><PythonSession pathname="/workspaces" navigate={navigate}>{()=> <p>Private</p>}</PythonSession></QueryClientProvider>);
 await waitFor(()=>expect(navigate).toHaveBeenCalledWith('/review/issues'));
});
it('falls back to SMART when the remembered membership is unavailable',async()=>{
 localStorage.setItem('workpal:last-workspace:user-1','revoked');
 list.mockResolvedValue([{id:'a',slug:'review',name:'TAP'},{id:'smart',slug:'workpal-team',name:'SMART'}]);const navigate=vi.fn();
 render(<QueryClientProvider client={new QueryClient()}><PythonSession pathname="/workspaces" navigate={navigate}>{()=> <p>Private</p>}</PythonSession></QueryClientProvider>);
 await waitFor(()=>expect(navigate).toHaveBeenCalledWith('/workpal-team/issues'));
});
it('does not reuse another account workspace preference',async()=>{
 localStorage.setItem('workpal:last-workspace:another-user','a');
 list.mockResolvedValue([{id:'a',slug:'review',name:'TAP'},{id:'smart',slug:'workpal-team',name:'SMART'}]);const navigate=vi.fn();
 render(<QueryClientProvider client={new QueryClient()}><PythonSession pathname="/workspaces" navigate={navigate}>{()=> <p>Private</p>}</PythonSession></QueryClientProvider>);
 await waitFor(()=>expect(navigate).toHaveBeenCalledWith('/workpal-team/issues'));
});
