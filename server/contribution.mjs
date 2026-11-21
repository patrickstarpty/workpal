// Port of the archived prototype's commit attribution rules.
import seed from './seed.json' with {type:'json'};
export function seedContribution() {
 return (seed.db.contributionCommits||[]).map(c=>({...c,at:new Date(c.at).toISOString(),fixture_source:'archived-prototype'}));
}
export function validateCommits(rows) {
 if(!Array.isArray(rows)||rows.length>20000)throw new Error('Provide a JSON array of up to 20,000 commits.');
 return rows.map(c=>{
  if(!c||typeof c.repository!=='string'||!c.repository.trim()||typeof c.sha!=='string'||!c.sha.trim()||typeof c.message!=='string'||typeof c.at!=='string'||!Number.isFinite(Date.parse(c.at))||!Number.isSafeInteger(c.additions)||c.additions<0||!Number.isSafeInteger(c.deletions)||c.deletions<0||!Number.isSafeInteger(c.additions+c.deletions))throw new Error('Each commit needs repository, sha, message, at (ISO date), and non-negative integer additions and deletions.');
  const explicit='agentLines' in c||'humanLines' in c;
  if(explicit&&(!Number.isSafeInteger(c.agentLines)||c.agentLines<0||!Number.isSafeInteger(c.humanLines)||c.humanLines<0||c.agentLines+c.humanLines>c.additions+c.deletions))throw new Error('Agent and human line counts must be non-negative integers and cannot exceed total changes.');
  return {repository:c.repository,sha:c.sha,message:c.message,at:c.at,additions:c.additions,deletions:c.deletions,...(explicit?{agentLines:c.agentLines,humanLines:c.humanLines}:{})};
 });
}
export function contribution(store,params,now=new Date()) {
 const days=Math.min(365,Math.max(1,Number(params.get('days'))||30)),project=params.get('project_id');
 let fmt;try{fmt=new Intl.DateTimeFormat('en-CA',{timeZone:params.get('tz')||'UTC',year:'numeric',month:'2-digit',day:'2-digit'});}catch{fmt=new Intl.DateTimeFormat('en-CA',{timeZone:'UTC',year:'numeric',month:'2-digit',day:'2-digit'});}
 const today=fmt.format(now),start=new Date(today+'T12:00:00Z');start.setUTCDate(start.getUTCDate()-days+1);
 const daily=Array.from({length:days},(_,i)=>{const d=new Date(start);d.setUTCDate(d.getUTCDate()+i);return {date:d.toISOString().slice(0,10),commits:0,agentLines:0,humanLines:0};});
 const calendar=new Map(daily.map(d=>[d.date,d])),all=new Map(store.list('issues').map(i=>[i.id,i])),projects=new Set(store.list('projects').map(p=>p.id));
 const issues=new Map([...all.values()].filter(i=>projects.has(i.project_id)&&(!project||i.project_id===project)).map(i=>[i.identifier.toUpperCase(),i]));
 const totals={commits:0,tickets:0,added:0,deleted:0,agentLines:0,humanLines:0},rows=new Map(),seen=new Set();let excluded=0;
 for(const c of store.get('contribution_data','workspace')?.commits||[]) {
  const at=new Date(c.at);if(!Number.isFinite(at.getTime())||at>now)continue;const day=calendar.get(fmt.format(at));if(!day)continue;
  const key=JSON.stringify([c.repository,c.sha]);if(seen.has(key))continue;seen.add(key);
  const matches=[...new Set(c.message.toUpperCase().match(/\b[A-Z][A-Z0-9]*-\d+\b/g)||[])].map(id=>issues.get(id)).filter(Boolean);if(!matches.length){excluded++;continue;}
  const assisted=/^Co-authored-by:\s*Workpal\s*<workpal@users\.noreply\.github\.com>\s*$/im.test(c.message);
  const total=c.additions+c.deletions,explicit=Number.isSafeInteger(c.agentLines)&&Number.isSafeInteger(c.humanLines)&&c.agentLines>=0&&c.humanLines>=0&&c.agentLines+c.humanLines<=total;
  const remainder=total-(explicit?c.agentLines+c.humanLines:0),agentLines=(explicit?c.agentLines:0)+(assisted?remainder:0),humanLines=total-agentLines;
  totals.commits++;totals.added+=c.additions;totals.deleted+=c.deletions;totals.agentLines+=agentLines;totals.humanLines+=humanLines;day.commits++;day.agentLines+=agentLines;day.humanLines+=humanLines;
  for(const issue of matches){
   if(!rows.has(issue.id)){
    let ancestor=issue,team='Unassigned';const visited=new Set();while(ancestor&&!visited.has(ancestor.id)){visited.add(ancestor.id);if(ancestor.assignee_type==='squad'){team=ancestor.assignee_id;break;}ancestor=all.get(ancestor.parent_issue_id);}
    rows.set(issue.id,{id:issue.id,identifier:issue.identifier,title:issue.title,team,commits:0,added:0,deleted:0,agentLines:0,humanLines:0});
   }
   const row=rows.get(issue.id);row.commits++;row.added+=c.additions;row.deleted+=c.deletions;row.agentLines+=agentLines;row.humanLines+=humanLines;
  }
 }
 totals.tickets=rows.size;
 return {totals,daily,rows:[...rows.values()].sort((a,b)=>(b.added+b.deleted)-(a.added+a.deleted)||a.id.localeCompare(b.id)),excluded};
}
