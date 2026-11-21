import {ProjectsPage} from '../../../packages/views/projects/components/projects-page';
import {ProjectDetail} from '../../../packages/views/projects/components/project-detail';
import {IssuesPage} from '../../../packages/views/issues/components/issues-page';
import {IssueDetailRoute} from '../../../packages/views/issues/components/issue-detail-route';
import {AgentsPage,AgentDetailPage,ChooseRuntimePage,ManualCreateAgentPage} from '@workpal/views/agents';
import {SkillsPage,SkillDetailPage} from '@workpal/views/skills';
import {SquadsPage,SquadDetailPage} from '@workpal/views/squads';
import {AutopilotsPage,AutopilotDetailPage} from '@workpal/views/autopilots/components';
import {RuntimesPage,RuntimeDetailPage} from '@workpal/views/runtimes';
import {MyIssuesPage} from '@workpal/views/my-issues';
import {AllViewsPage} from '@workpal/views/issue-views';
import {MemberDetailPage} from '@workpal/views/members';
import {InboxPage} from '@workpal/views/inbox';
import {ChatPage} from '@workpal/views/chat';
import {SettingsPage} from '@workpal/views/settings';
import {DashboardPage} from '@workpal/views/dashboard';

export function LocalPage({pathname,workspaceSlug}:{pathname:string;workspaceSlug:string}) {
  let segments:string[];
  try {segments=pathname.split('/').filter(Boolean).map(decodeURIComponent);}
  catch {return <MissingPage workspaceSlug={workspaceSlug}/>;}
  const [,page,id,child]=segments;
  if(segments[0]!==workspaceSlug)return <MissingPage workspaceSlug={workspaceSlug}/>;
  switch(page){
    case undefined:return <IssuesPage/>;
    case 'projects':return id?<ProjectDetail key={id} projectId={id}/>:<ProjectsPage/>;
    case 'issues':return id?<IssueDetailRoute key={id} routeId={id}/>:<IssuesPage/>;
    case 'agents':
      if(id==='new')return child==='manual'?<ManualCreateAgentPage/>:child?<MissingPage workspaceSlug={workspaceSlug}/>:<ChooseRuntimePage/>;
      return id?<AgentDetailPage key={id} agentId={id}/>:<AgentsPage/>;
    case 'skills':return id?<SkillDetailPage key={id} skillId={id}/>:<SkillsPage/>;
    case 'squads':return id?<SquadDetailPage key={id}/>:<SquadsPage/>;
    case 'autopilots':return id?<AutopilotDetailPage key={id} autopilotId={id}/>:<AutopilotsPage/>;
    case 'runtimes':return id?<RuntimeDetailPage key={id} runtimeId={id}/>:<RuntimesPage cloudRuntimeEnabled={false}/>;
    case 'members':return id?<MemberDetailPage key={id} userId={id}/>:<MissingPage workspaceSlug={workspaceSlug}/>;
    case 'my-issues':return <MyIssuesPage/>;
    case 'views':return <AllViewsPage/>;
    case 'inbox':return <InboxPage/>;
    case 'chat':return <ChatPage/>;
    case 'settings':return <SettingsPage/>;
    case 'changelog':return <LocalChangelog/>;
    case 'usage':case 'dashboard':return <DashboardPage/>;
    default:return <MissingPage workspaceSlug={workspaceSlug}/>;
  }
}
function MissingPage({workspaceSlug}:{workspaceSlug:string}){return <section role="status" className="m-auto p-8 text-center"><h1 className="text-lg font-semibold">Page unavailable</h1><p className="mt-2 text-muted-foreground">This page is not available in this workspace.</p><a className="mt-4 inline-block underline" href={`#/${encodeURIComponent(workspaceSlug)}/projects`}>Back to projects</a></section>;}

function LocalChangelog(){return <section className="mx-auto w-full max-w-3xl overflow-auto p-6"><h1 className="text-lg font-semibold">Changelog</h1><article className="mt-6 rounded-lg border bg-card p-5"><time className="text-caption text-muted-foreground">November 21, 2026</time><h2 className="mt-2 text-body font-medium">Analytics and workspace improvements</h2><ul className="mt-3 list-disc space-y-2 pl-5 text-body text-muted-foreground"><li>Added Contribution alongside Usage and Errors, with commit activity, ticket attribution and JSON import.</li><li>Connected Analytics date and project filters to local usage data.</li><li>Added ticket descriptions, review notes and activity discussions.</li><li>Restored search, Ask Workpal, skill detail and squad navigation.</li><li>Connected documentation locally and removed unavailable community and desktop links.</li></ul></article></section>;}
