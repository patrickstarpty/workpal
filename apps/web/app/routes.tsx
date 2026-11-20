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

export function LocalPage({pathname}:{pathname:string}) {
  let segments:string[];
  try {segments=pathname.split('/').filter(Boolean).map(decodeURIComponent);}
  catch {return <MissingPage/>;}
  const [,page,id,child]=segments;
  if(segments[0]!=='review')return <MissingPage/>;
  switch(page){
    case undefined:case 'projects':return id?<ProjectDetail key={id} projectId={id}/>:<ProjectsPage/>;
    case 'issues':return id?<IssueDetailRoute key={id} routeId={id}/>:<IssuesPage/>;
    case 'agents':
      if(id==='new')return child==='manual'?<ManualCreateAgentPage/>:child?<MissingPage/>:<ChooseRuntimePage/>;
      return id?<AgentDetailPage key={id} agentId={id}/>:<AgentsPage/>;
    case 'skills':return id?<SkillDetailPage key={id} skillId={id}/>:<SkillsPage/>;
    case 'squads':return id?<SquadDetailPage key={id}/>:<SquadsPage/>;
    case 'autopilots':return id?<AutopilotDetailPage key={id} autopilotId={id}/>:<AutopilotsPage/>;
    case 'runtimes':return id?<RuntimeDetailPage key={id} runtimeId={id}/>:<RuntimesPage cloudRuntimeEnabled={false}/>;
    case 'members':return id?<MemberDetailPage key={id} userId={id}/>:<MissingPage/>;
    case 'my-issues':return <MyIssuesPage/>;
    case 'views':return <AllViewsPage/>;
    case 'inbox':return <InboxPage/>;
    case 'chat':return <ChatPage/>;
    case 'settings':return <SettingsPage/>;
    case 'usage':case 'dashboard':return <DashboardPage/>;
    default:return <MissingPage/>;
  }
}
function MissingPage(){return <section role="status" className="m-auto p-8 text-center"><h1 className="text-lg font-semibold">Page unavailable</h1><p className="mt-2 text-muted-foreground">This page is not available in this workspace.</p><a className="mt-4 inline-block underline" href="#/review/projects">Back to projects</a></section>;}
