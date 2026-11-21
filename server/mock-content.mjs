// Authored review fixtures, not execution telemetry. Keep out of production backends.
const details = {
 'TAP-029': ['A duplicate upload currently looks like a fresh document until parsing finishes. We need to cover the unhappy paths before opening ingestion to the rest of the team.', '## Cases to cover\n- Empty PDF: explain the problem before adding a queue entry.\n- Same file uploaded twice: offer the existing document.\n- Connection drops halfway through: keep the filename and allow retry.\n- Password-protected PDF: request an unlocked copy.\n\n## Acceptance\nRetry must not create another document. Keyboard focus returns to the failed row, and other uploads continue normally.', 'Please include a scanned PDF as well; a text-only fixture will miss the OCR path.', 'Agreed. Keep cancellation separate from parse failure so we can tell which action the user took.'],
 'TAP-028': ['Readers need to check where an answer came from without losing their place in the conversation.', '## Review scope\nOpen a citation beside the answer, highlight the quoted passage and keep the source title visible. Returning to chat should restore scroll position.\n\nStill to review: two citations pointing to different pages of the same PDF.', 'Can the drawer open directly on the cited page? Starting at page one makes longer reports hard to check.'],
 'TAP-033': ['An upload interrupted by sleep or a network switch can remain on “Uploading” after reconnecting.', '## Decision needed\nShould a partially received file expire after one day or stay resumable for a week? Retention affects both storage cleanup and the recovery message.\n\nBlocked until that policy is agreed. Keep the original filename and document ID on retry.', 'Use a one-day recovery window for the first release. Please confirm whether the storage cleanup job can use the same cutoff.'],
 'TAP-1004': ['Closing the source drawer sends keyboard focus to the page body. Return it to the citation that opened the drawer.', '', 'Also check Escape after switching between two sources.'],
 'TAP-1013': ['Retrying a failed parser job should reuse the existing document rather than append another row.', '## Approach\nKeep document identity separate from parse attempts. A retry creates a new attempt and clears the displayed error only after the queue accepts it.\n\n## Acceptance\n- Repeated clicks enqueue one attempt.\n- Existing source links stay valid.\n- A second failure shows the latest reason.'],
 'TAP-1020': ['Archived documents still appear in retrieval candidates for older conversations.', '## Blocker\nThe archive flag is applied in the library query but not in the retrieval index. Agree on whether existing citations remain readable before filtering the index.\n\nNew answers must not cite archived documents. Historical answers should retain their citation text.', 'I would keep historical citations readable with an archived indicator. Removing them would make earlier answers impossible to audit.'],
 'TAP-1022': ['Short queries such as “SSO” return either no documents or too many weak matches.', '## Review notes\nUse a small set of navigation, acronym and question queries. Compare the first few results with a reviewer-approved list, including queries that should return nothing.\n\nDo not lower the threshold globally: document titles and body passages need separate treatment.', 'Please add an exact title match and a misspelled acronym to the review set.', 'The empty-result message should still suggest changing the query; do not fill the list with unrelated documents.'],
 'TAP-1023': ['Opening a search result clears the selected project filter when returning to results.', '## Pending decision\nStore filters in the URL or per conversation? URL state would allow sharing a filtered result set, but we need a rule for projects the recipient cannot access.', 'Prefer URL state. Ignore inaccessible project IDs and show the remaining accessible results.'],
 'DEV-1032': ['Repository setup assumes the default branch is named main. Some existing repositories use trunk or a release branch.', '## Acceptance\nRead the default branch from repository metadata. Show the chosen branch before indexing and allow an override. An empty repository should offer a clear next step.\n\n## Review\nConfirm that renaming the branch after setup does not silently change the indexed revision.', 'Please keep the branch override visible in the confirmation step.'],
 'DEV-1044': ['A runner disconnect currently leaves the log viewer waiting indefinitely.', '## Recovery\nPersist received chunks with sequence numbers. On reconnect, resume from the last acknowledged chunk without duplicate lines.\n\nBlocked on the retention decision: seven days for failed jobs, or the same policy as successful builds?', 'Failed jobs need longer retention for investigation. Let’s settle that policy before adding the cleanup rule.'],
 'DEV-1057': ['Do not promote a release while a required dependency is blocked.', 'Show which dependency prevents promotion and link to its ticket. Re-check at approval time because the dependency may change while the dialog is open.'],
 'DEV-1059': ['A staged rollout can be healthy in one environment and paused in another. A single progress bar hides this distinction.', '## Scope\nShow each environment with its current step, the last update and any reason for pausing.\n\n## Acceptance\nA paused step must not appear as failed. Refreshing the page keeps the same rollout selected. Provide a link to rollback instructions beside the affected environment.', 'Keep timestamps absolute in the detail view so people in different time zones can compare notes.'],
 'SKILL-1070': ['Teams need repeatable skill behavior across a release. Pin an installed skill to an explicit version.', 'Updating should be an intentional action with a changelog preview. A pinned version remains selected when a newer version is published.'],
 'SKILL-1071': ['Before updating a skill, explain which inputs, permissions and output fields have changed.', '## Acceptance\nCompare the installed and selected versions. Separate permission additions from text-only documentation changes. An empty changelog should say that release notes are unavailable.\n\nOpen question: should a new permission always require a second confirmation?', 'Yes for a new permission. A wording-only change should use the normal update action.'],
 'SKILL-1072': ['Keep the last installed skill version available so an unsuccessful update can be rolled back.', '', 'Please check that rollback restores the previous configuration too, not just the version number.'],
};
export function enrichIssues(issues) {
 return issues.map((issue,i)=>{
  const custom=details[issue.id];
  const children=issues.filter(r=>r.parent_issue_id===issue.id);
  let description;
  if(custom) description=[custom[0],custom[1]].filter(Boolean).join('\n\n');
  else if(children.length) description=`Coordinate ${issue.title.replace(/ release$/i,'').toLowerCase()} across the team.\n\n## Scope\n${children.slice(0,5).map(c=>`- ${c.title}`).join('\n')}\n\nClose this milestone when its child tickets are reviewed and remaining follow-ups have owners.`;
  else {
   const summary=(issue.description||issue.title).split(/(?<=\.)\s/)[0];
   const note=issue.status==='blocked'?'## Open decision\nConfirm the expected behavior with the project owner before continuing. Record the agreed edge case here so review can use the same expectation.':issue.status==='in_review'?'## Review\nCheck the main flow and the failure path. Keep existing project permissions intact and leave any follow-up outside this change as a separate ticket.':issue.status==='done'?'## Handoff\nKeep this change in the next regression pass, including the empty-state path.':`## Scope\nKeep this change focused on “${issue.title.replace(/ · .*$/,'')}”. Preserve the current behavior for other ${issue.project_id||'workspace'} flows.`;
   description=summary+(i%4===0?'':`\n\n${note}`)+(i%7===0?'\n\n## Acceptance\n- The state survives a page refresh.\n- Failure leaves a clear recovery action.\n- The flow works with keyboard navigation.':'');
  }
  const historicalDate=issue.title.match(/ · (\d{4}-\d{2}-\d{2})$/)?.[1];
  const created_at=historicalDate?historicalDate+'T08:00:00.000Z':new Date(Date.UTC(2026,7,1+i%19,8)).toISOString();
  return {...issue,description,created_at};
 });
}
export function makeComments(issues) {
 return issues.flatMap((issue,i)=>{
  const lines=details[issue.id]?.slice(2)||[];
  // Most small tickets need no discussion. Larger tickets have a short, uneven history.
  if(!lines.length&&i%9===0)lines.push(issue.status==='blocked'?'Leaving this blocked until the scope decision is recorded. Please keep the owner assigned.':`Please keep the review focused on ${issue.title.replace(/ · .*$/,'').toLowerCase()}. Any adjacent cleanup can be a follow-up.`);
  return lines.map((content,n)=>({id:`mock-comment-${issue.id}-${n}`,issue_id:issue.id,author_type:'member',author_id:'patrick',content,type:'comment',parent_id:null,reactions:[],attachments:[],created_at:new Date(Date.UTC(2026,10,18+n,9+i%8)).toISOString(),updated_at:new Date(Date.UTC(2026,10,18+n,9+i%8)).toISOString(),fixture_source:'authored-review-v1'}));
 });
}
export function makeAnalytics(issues,agents,now=new Date()) {
 const rows=[]; const eligible=issues.filter(i=>!i.parent_issue_id?.startsWith('missing')&&i.project_id);
 for(let day=0;day<90;day++) {
  const date=new Date(now);date.setUTCDate(date.getUTCDate()-day);
  const weekend=[0,6].includes(date.getUTCDay());
  const count=weekend?2+day%4:9+(day*7)%19;
  for(let n=0;n<count;n++) {
   const available=eligible.filter(i=>new Date(i.created_at)<=date);
   if(!available.length)continue;
   const issue=available[(day*17+n*13)%available.length], agent=agents.find(a=>a.id===issue.assignee_id)||agents[(day+n*n)%agents.length];
   const k=day*31+n*17, failed=k%17===0, cancelled=!failed&&k%41===0;
   rows.push({id:`mock-run-${day}-${n}`,issue_id:issue.id,project_id:issue.project_id,agent_id:agent.id,completed_at:new Date(date.getTime()-n*197000).toISOString(),provider:n%3?'anthropic':'openai',model:n%3?'claude-sonnet-4-6':'gpt-4.1',input_tokens:2100+k%18000,output_tokens:340+k%3900,cache_read_tokens:k%2?11000+k%26000:0,cache_write_tokens:k%5?0:1800+k%4000,total_seconds:failed?35+k%95:75+k%1100,task_count:1,failed_count:failed?1:0,cancelled_count:cancelled?1:0,failure_reason:failed?['agent_error.provider_capacity_or_rate_limit','timeout','runtime_offline'][k%3]:'',fixture_source:'authored-review-v1'});
  }
 }
 return rows;
}
export function dashboardRows(store,path,params,now=new Date()) {
 const days=Math.min(365,Math.max(1,Number(params.get('days'))||30));
 let formatter;try {formatter=new Intl.DateTimeFormat('en-CA',{timeZone:params.get('tz')||'UTC',year:'numeric',month:'2-digit',day:'2-digit'});}catch{formatter=new Intl.DateTimeFormat('en-CA',{timeZone:'UTC',year:'numeric',month:'2-digit',day:'2-digit'});}
 const dayKey=d=>formatter.format(d); const today=dayKey(now),cutoff=new Date(today+'T12:00:00Z');cutoff.setUTCDate(cutoff.getUTCDate()-days+1);const start=cutoff.toISOString().slice(0,10);
 const project=params.get('project_id'), validProjects=new Set(store.list('projects').map(p=>p.id)), validIssues=new Set(store.list('issues').map(i=>i.id));
 const rows=store.list('analytics_runs').filter(r=>validProjects.has(r.project_id)&&validIssues.has(r.issue_id)&&(!project||r.project_id===project)&&dayKey(new Date(r.completed_at))>=start&&dayKey(new Date(r.completed_at))<=today);
 const usage=path.includes('/usage/'),failure=path.includes('/failures/'),daily=path.endsWith('/daily');const grouped=new Map();
 for(const row of rows){
  const dimensions=daily?{date:dayKey(new Date(row.completed_at))}:{agent_id:row.agent_id};
  if(usage)Object.assign(dimensions,{provider:row.provider,model:row.model});
  if(failure)dimensions.failure_reason=row.failure_reason;
  const key=JSON.stringify(dimensions),out=grouped.get(key)||{...dimensions};
  const fields=usage?['input_tokens','output_tokens','cache_read_tokens','cache_write_tokens','task_count']:failure?['task_count']:['total_seconds','task_count','failed_count','cancelled_count'];
  for(const field of fields)out[field]=(out[field]||0)+row[field];
  grouped.set(key,out);
 }
 return [...grouped.values()].sort((a,b)=>(a.date||a.agent_id).localeCompare(b.date||b.agent_id));
}
