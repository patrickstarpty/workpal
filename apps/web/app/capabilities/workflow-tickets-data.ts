import {getApi} from '@workpal/core/api';
export const workflowSlug = 'workpal-team';
export type WorkflowTicket = {id:string; identifier:string; title:string; status:string; metadata:Record<string,string | number | boolean>};
export async function loadWorkflowTickets(signal: AbortSignal): Promise<WorkflowTicket[]> {
 const api = getApi();
 const token = api.getToken();
 const response = await fetch(`${api.getBaseUrl()}/api/issues?project_id=flexible-workflow&limit=10000`, {
  credentials:'include', signal, headers:{'X-Workspace-Slug':workflowSlug,...(token ? {Authorization:`Bearer ${token}`} : {})},
 });
 if(!response.ok) throw new Error('Unable to load workflow tickets');
 const data = await response.json();
 if(!Array.isArray(data.issues)) throw new Error('Invalid ticket response');
 return data.issues;
}
