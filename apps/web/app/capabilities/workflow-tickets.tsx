import {useEffect, useState} from 'react';
import {Button} from '@workpal/ui/components/ui/button';
import {loadWorkflowTickets, workflowSlug, type WorkflowTicket} from './workflow-tickets-data';
const statuses = {backlog:'Backlog',todo:'Todo',in_progress:'In Progress',in_review:'In Review',done:'Done',blocked:'Blocked',cancelled:'Cancelled'};
export function WorkflowTickets({stage}:{stage:string}) {
 const [tickets,setTickets]=useState<WorkflowTicket[]>([]);
 const [state,setState]=useState<'loading'|'ready'|'error'>('loading');
 const [attempt,setAttempt]=useState(0);
 const [status,setStatus]=useState('all');
 const [allStages,setAllStages]=useState(false);
 useEffect(()=>{
  const controller=new AbortController();
  setState('loading');
  loadWorkflowTickets(controller.signal).then(rows=>{if(!controller.signal.aborted){setTickets(rows);setState('ready');}},()=>{if(!controller.signal.aborted)setState('error');});
  return ()=>controller.abort();
 },[attempt]);
 const matching=tickets.filter(ticket=>(allStages || ticket.metadata?.workflow_stage===stage) && (status==='all' || ticket.status===status));
 return <section className="panel" aria-label="Workflow tickets">
  <h2>{allStages ? 'Workflow tickets' : 'Work in this stage'}</h2><p>A ticket owns an outcome. Continue across stages, start here, or hand off related work.</p>
  <div className="chips"><label>Work status <select aria-label="Work status" value={status} onChange={event=>setStatus(event.target.value)}><option value="all">All statuses</option>{Object.entries(statuses).map(([key,name])=><option key={key} value={key}>{name}</option>)}</select></label>
  <label><input type="checkbox" checked={allStages} onChange={event=>setAllStages(event.target.checked)}/> Include all stages</label>
  <a className="chip" href={`#/${workflowSlug}/issues`}>Open SMART workspace</a></div>
  {state==='loading' ? <p role="status">Loading workflow tickets…</p> : state==='error' ? <><p role="alert">Unable to load workflow tickets.</p><Button onClick={()=>setAttempt(value=>value+1)}>Try again</Button></> : <><p>{matching.length} tickets</p>{matching.length ? <div className="artifact-outline">{matching.map(ticket=><article key={ticket.id}>
   <h3><a href={`#/${workflowSlug}/issues/${encodeURIComponent(ticket.id)}`}>{ticket.identifier} · {ticket.title}</a></h3>
   <p>{statuses[ticket.status as keyof typeof statuses] ?? ticket.status} · {String(ticket.metadata?.workflow_stage ?? '')} · {String(ticket.metadata?.work_scope ?? '')}</p>
  </article>)}</div> : <p>No tickets match this stage and status.</p>}</>}
 </section>;
}
