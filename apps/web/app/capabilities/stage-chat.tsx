import {useEffect, useRef, useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {workspaceListOptions} from '@workpal/core/workspace/queries';
import {getCurrentSlug, setCurrentWorkspace} from '@workpal/core/platform';
import {WorkspaceSlugProvider} from '@workpal/core/paths';
import {DRAFT_NEW_SESSION, useChatStore} from '@workpal/core/chat';
import {ChatWindow} from '@workpal/views/chat';
import {AppBottomBar} from '@workpal/views/layout';
import {Button} from '@workpal/ui/components/ui/button';
import {Dialog, DialogContent, DialogHeader, DialogTitle} from '@workpal/ui/components/ui/dialog';
import {stages} from './data';

const prompts = [
  'Help me clarify my intent, scope and success criteria.',
  'Help me turn my requirements into a spec with acceptance criteria.',
  'Help me implement a change from my spec or issue.',
  'Help me test and review an implementation.',
  'Help me prepare a release and review deployment readiness.',
  'Help me investigate a problem or improve an existing system.',
];
export function stageDraft(index: number) {
  return `[${String(index + 1).padStart(2, '0')} · ${stages[index]!.name}] ${prompts[index]}\n\n`;
}

function withStage(draft: string, stage: number) {
  const previous = stages.map((_, index) => stageDraft(index)).find(prefix => draft.startsWith(prefix));
  return stageDraft(stage) + (previous ? draft.slice(previous.length) : draft);
}

export function StageChat({stage, onClose, workspaceId, onWorkspaceChange}: {stage: number | null; onClose: ()=>void; workspaceId?: string | null; onWorkspaceChange?: (id:string)=>void}) {
  useEffect(() => {
    const trigger = document.activeElement;
    return () => { if (trigger instanceof HTMLElement && trigger.isConnected) trigger.focus({preventScroll: true}); };
  }, []);
  const query = useQuery({...workspaceListOptions(), retry: false});
  const [chosen, setChosen] = useState<string | null>(null);
  const workspace = query.data?.find(w=>w.id===(chosen ?? workspaceId)) ?? (query.data?.length===1 ? query.data[0] : undefined);
  if (!workspace) return <Dialog open onOpenChange={open=>{if(!open)onClose();}}><DialogContent><DialogHeader><DialogTitle>Choose a workspace</DialogTitle></DialogHeader>
    {query.isPending ? <p role="status">Loading workspaces…</p> : query.isError ? <><p role="alert">Unable to load workspaces.</p><Button onClick={()=>void query.refetch()}>Try again</Button></> : query.data?.length ? query.data.map(w=><Button key={w.id} variant="outline" onClick={()=>{setChosen(w.id);onWorkspaceChange?.(w.id);}}>{w.name}</Button>) : <p>Create a workspace using Enter Workspace to start a conversation.</p>}
  </DialogContent></Dialog>;
  return <BoundStageChat key={workspace.id} workspace={workspace} stage={stage} onClose={onClose}/>;
}
function BoundStageChat({workspace, stage, onClose}: {workspace:{id:string;slug:string;name:string};stage:number | null;onClose:()=>void}) {
  const [ready, setReady] = useState(false);
  const open = useChatStore(s=>s.isOpen);
  const initialStage = useRef(stage);
  useEffect(()=>{
    setCurrentWorkspace(workspace.slug, workspace.id);
    let cancelled = false;
    // Workspace stores hydrate in a microtask. Read the destination draft afterwards.
    queueMicrotask(() => {
      if (cancelled) return;
      const chat = useChatStore.getState();
      chat.startNewChat();
      if (initialStage.current !== null) chat.setInputDraft(DRAFT_NEW_SESSION, withStage(chat.inputDrafts[DRAFT_NEW_SESSION] ?? '', initialStage.current));
      setReady(true);
    });
    return () => {
      cancelled = true;
      if (getCurrentSlug() === workspace.slug) {
        useChatStore.getState().setOpen(false);
        setCurrentWorkspace(null, null);
      }
    };
  },[workspace.id,workspace.slug]);
  useEffect(()=>{if(ready&&!open)onClose();},[ready,open,onClose]);
  if(!ready)return null;
  return <WorkspaceSlugProvider slug={workspace.slug}><div className="fixed inset-x-0 bottom-0 z-40 bg-app-shell"><AppBottomBar/></div><div className="fixed inset-0 z-50 pointer-events-none"><ChatWindow/></div></WorkspaceSlugProvider>;
}
