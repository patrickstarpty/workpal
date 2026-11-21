import {useEffect, useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {workspaceListOptions} from '@workpal/core/workspace/queries';
import {setCurrentWorkspace} from '@workpal/core/platform';
import {WorkspaceSlugProvider} from '@workpal/core/paths';
import {AppBottomBar} from '@workpal/views/layout';
import {FloatingChat, AskWorkpalButton} from '@workpal/views/chat';

import {StageChat} from './stage-chat';

// Use the same workspace-bound launcher, history and responsive window as the app shell.
export function CapabilityChat({workspaceId, onWorkspaceChange}: {workspaceId: string | null; onWorkspaceChange: (id:string)=>void}) {
  const [choosing, setChoosing] = useState(false);
  const {data: workspaces} = useQuery(workspaceListOptions());
  const workspace = workspaces?.find(item => item.id === workspaceId);
  if (choosing) return <StageChat stage={null} workspaceId={workspaceId} onWorkspaceChange={onWorkspaceChange} onClose={()=>setChoosing(false)}/>;
  return workspace ? <BoundChat key={workspace.id} workspace={workspace}/> : <div className="fixed inset-x-0 bottom-0 z-40 flex h-8 items-center justify-end bg-app-shell px-[18px]"><AskWorkpalButton onClick={()=>setChoosing(true)}/></div>;
}
function BoundChat({workspace}: {workspace: {id:string;slug:string}}) {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    setCurrentWorkspace(workspace.slug, workspace.id);
    setReady(true);
  }, [workspace.id, workspace.slug]);
  if (!ready) return null;
  return <WorkspaceSlugProvider slug={workspace.slug}>
    <div className="fixed inset-x-0 bottom-0 z-40 bg-app-shell"><AppBottomBar/></div>
    <FloatingChat/>
  </WorkspaceSlugProvider>;
}
