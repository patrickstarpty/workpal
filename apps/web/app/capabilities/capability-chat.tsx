import {useEffect, useState} from 'react';
import {useQuery} from '@tanstack/react-query';
import {workspaceListOptions} from '@workpal/core/workspace/queries';
import {getCurrentSlug, setCurrentWorkspace} from '@workpal/core/platform';
import {WorkspaceSlugProvider} from '@workpal/core/paths';
import {AppBottomBar} from '@workpal/views/layout';
import {FloatingChat} from '@workpal/views/chat';

// Use the same workspace-bound launcher, history and responsive window as the app shell.
export function CapabilityChat() {
  const {data: workspaces} = useQuery(workspaceListOptions());
  const workspace = workspaces?.find(item => item.slug === getCurrentSlug()) ?? workspaces?.[0];
  return workspace ? <BoundChat key={workspace.id} workspace={workspace}/> : null;
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
