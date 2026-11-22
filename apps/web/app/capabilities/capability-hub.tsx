import {useLayoutEffect, useRef, useState} from 'react';
import {Button} from '@workpal/ui/components/ui/button';
import {WorkpalIcon} from '@workpal/ui/components/common/workpal-icon';
import {WorkpalWordmark} from '@workpal/ui/components/common/workpal-wordmark';
import {Overview} from './overview';
import {SkillHub} from './skill-hub';
import {AgentTeam} from './agent-team';
import {capabilityPath, type CapabilityView} from './routes';
import './capabilities.css';
import {StageChat} from './stage-chat';
import {CapabilityChat} from './capability-chat';

export function CapabilityHub({view, navigate, enterWorkspace}: {view: CapabilityView; navigate: (path: string) => void; enterWorkspace: () => void}) {
  const [workspaceId, setWorkspaceId] = useState<string | null>(null);
  const [chatStage, setChatStage] = useState<number | null>(null);
  const [openingSkillId, setOpeningSkillId] = useState<string | null>(null);
  const content = useRef<HTMLElement>(null);
  const previousView = useRef<CapabilityView | null>(null);
  useLayoutEffect(() => {
    if (previousView.current === view) return;
    previousView.current = view;
    content.current?.scrollTo({top: 0});
    // Cross-page skill links focus their specific detail after it mounts.
    if (view === 'skills' && openingSkillId) return;
    content.current?.focus({preventScroll: true});
  }, [view, openingSkillId]);
  const changeView = (next: CapabilityView) => {setOpeningSkillId(null); navigate(capabilityPath(next));};
  const openSkill = (id: string) => {setOpeningSkillId(id); navigate(capabilityPath('skills'));};
  return <div className="capability-shell"><div className="capability-hub">
    <a className="capability-skip" href="#capability-content" onClick={event => {event.preventDefault(); document.getElementById('capability-content')?.focus();}}>Skip to content</a>
    <header className="masthead">
      <a className="brand" href="#/home" aria-label="Workpal overview" onClick={event => {event.preventDefault(); changeView('overview');}}><WorkpalIcon size={28} aria-hidden="true"/><WorkpalWordmark className="capability-wordmark" aria-hidden="true"/></a>
      <nav className="nav" aria-label="Capabilities">{([['overview', 'Overview'], ['skills', 'Skill Hub'], ['team', 'Agent Team']] as const).map(([id, label]) => <Button key={id} variant="ghost" size="sm" aria-current={view === id ? 'page' : undefined} data-nav={id} onClick={() => changeView(id)}>{label}</Button>)}</nav>
      <Button size="sm" onClick={enterWorkspace}>Enter Workspace</Button>
    </header>
    <main ref={content} id="capability-content" className="capability-content" data-mc="page" tabIndex={-1}>
      {view === 'overview' ? <Overview onStartStage={setChatStage} onOpenSkill={openSkill} onNavigate={next => {content.current?.scrollTo({top: 0, behavior: 'instant'}); changeView(next);}}/> : view === 'skills' ? <SkillHub initialSkillId={openingSkillId}/> : <AgentTeam onOpenSkill={openSkill}/>}
    </main>
  </div>{chatStage===null && <CapabilityChat workspaceId={workspaceId} onWorkspaceChange={setWorkspaceId}/>}{chatStage!==null && <StageChat workspaceId={workspaceId} onWorkspaceChange={setWorkspaceId} stage={chatStage} onClose={()=>setChatStage(null)}/>}</div>;
}
