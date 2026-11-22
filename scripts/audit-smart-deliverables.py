"""Read-only audit of every SMART ticket and its individual Activity claims."""
import json
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import select
from workpal_backend.config import Settings
from workpal_backend.infrastructure.database import Database
from workpal_backend.workspaces.models import workspaces
from workpal_backend.workspace_content.repository import list_records

out=Path('docs/handoffs/smart-deliverables')
out.mkdir(parents=True,exist_ok=True)
db=Database(Settings())
try:
 with db.transaction() as session:
  ws=session.execute(select(workspaces).where(workspaces.c.slug=='workpal-team')).mappings().one()
  kinds={kind:list_records(session,ws['id'],kind) for kind in ('issues','comments','activities','task_runs','attachments','attachment_contents','delivery_revisions','delivery_reviews')}
  tickets=[]
  for issue in kinds['issues']:
   related={kind:[row for row in rows if row.get('issue_id')==issue['id']] for kind,rows in kinds.items() if kind not in ('issues','attachment_contents')}
   ids={a['id'] for a in related['attachments']}
   related['attachment_contents']=[r for r in kinds['attachment_contents'] if r['id'] in ids]
   tickets.append({'issue':issue,**related})
  report={'audited_at':datetime.now(timezone.utc).isoformat(),'workspace':ws['slug'],'tickets':tickets}
  (out/'inventory.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
  lines=['# SMART deliverable audit','', 'Read-only inventory. Counts are navigation aids, not evidence of completion.','']
  for ticket in tickets:
   issue=ticket['issue'];lines += [f"## {issue.get('identifier',issue['id'])}: {issue['title']}",'',f"Status: {issue.get('status')}; activity comments: {len(ticket['comments'])}; runs: {len(ticket['task_runs'])}; attachments: {len(ticket['attachments'])}.",'']
   for comment in ticket['comments']:
    lines += [f"- Activity `{comment['id']}`; Run `{comment.get('source_task_id','none')}`; attachments: {', '.join(a['id'] for a in comment.get('attachments',[])) or 'none'}. Claim: "+comment.get('content','').replace('\n',' ')[:350]]
   lines += ['']
  (out/'activity-audit.md').write_text('\n'.join(lines)+'\n')
  print(json.dumps({'tickets':len(tickets),'comments':sum(len(t['comments']) for t in tickets),'output':str(out)}))
finally: db.close()
