"""Assign existing SMART work to squads or individual agents; do not execute runs."""
import sqlite3
import json
from datetime import datetime, timezone
from sqlalchemy import select
from workpal_backend.config import Settings
from workpal_backend.infrastructure.database import Database
from workpal_backend.auth.dependencies import Principal
from workpal_backend.auth.models import users
from workpal_backend.workspaces.models import workspaces
from workpal_backend.workspace_content.repository import get_record,put_record,list_records
from workpal_backend.workspace_content.routes import save_collection

ASSIGNMENTS=[('squad','discovery'),('agent','design-role'),('squad','delivery'),('squad','assurance'),
 ('squad','operations'),('squad','experiments'),('squad','delivery'),('agent','design-role'),
 ('agent','implementation'),('agent','verifier'),('squad','operations'),('squad','operations'),
 ('squad','discovery'),('agent','design-role'),('squad','delivery'),('squad','assurance'),
 ('squad','operations'),('squad','experiments'),('squad','discovery'),('squad','discovery'),('squad','delivery')]

def assign(session):
 workspace=dict(session.execute(select(workspaces).where(workspaces.c.slug=='workpal-team')).mappings().one())
 owner=session.execute(select(users).where(users.c.email=='workpal@fwd.com')).mappings().one()
 wid=workspace['id'];principal=Principal(owner['id']);counts={'squad':0,'agent':0}
 for number,(kind,role) in enumerate(ASSIGNMENTS,1):
  iid=f'workflow-work-{number:02d}';cid='smart-coordination-v1-'+iid
  issue=get_record(session,wid,'issues',iid)
  if not issue:raise RuntimeError('Expected SMART ticket '+iid)
  target=get_record(session,wid,'squads' if kind=='squad' else 'agents','workflow-'+role)
  if not target:raise RuntimeError('Missing assignee '+role)
  if get_record(session,wid,'comments',cid):continue
  save_collection(session,workspace,principal,'issues',{'assignee_type':kind,'assignee_id':target['id']},issue)
  if kind=='squad':
   leader=get_record(session,wid,'agents',target['leader_id'])
   roster=[get_record(session,wid,'agents',m['member_id']) for m in target['member_preview']]
   if not leader or any(a is None for a in roster):raise RuntimeError('Incomplete squad membership')
   body=f"**Responsible squad:** {target['name']}\n\n**Coordination lead:** {leader['name']} — organize scoped work, request specialist review and keep the acceptance decision with the ticket owner.\n\n## Available contributors\n"+'\n'.join(f"- **{a['name']}:** {a.get('description','')}" for a in roster)
   body+='\n\n## Work assignment\nThe squad owns this ticket’s outcome. Individual runs and comments identify who actually performed each action; squad membership alone does not imply participation. A focused task may be assigned directly to an agent, with the handoff recorded here.'
  else:
   body=f"**Direct assignee:** {target['name']}\n\n**Responsibility:** {target.get('description','')}\n\nThis scope can be handled directly without creating a squad. Request reviewers or hand work to a squad when needed; keep the result and review attached to this ticket."
  body+='\n\n## Acceptance and evidence\n'+issue['metadata']['completion_criteria']+'\n\nAttach the relevant specification, change/review or verification report to the work that produces it. Assignment does not start a model run or change the ticket’s completion state.'
  stamp=datetime.now(timezone.utc).isoformat()
  put_record(session,wid,'comments',{'id':cid,'workspace_id':wid,'issue_id':iid,'type':'comment','author_type':'member','author_id':owner['id'],
   'content':'## Work coordination\n\n'+body,'created_at':stamp,'updated_at':stamp,'revision':1,'attachments':[],'reactions':[],'parent_id':None})
  counts[kind]+=1
 return counts

if __name__=='__main__':
 settings=Settings()
 if not settings.dev_auth:raise RuntimeError('Development authentication required')
 db=Database(settings)
 try:
  backup=str(db.engine.url.database)+'.before-smart-coordination-'+datetime.now().strftime('%Y%m%d%H%M%S%f')
  with sqlite3.connect(db.engine.url.database) as src,sqlite3.connect(backup) as dst:src.backup(dst)
  with db.transaction() as session:result=assign(session)
  print(json.dumps({**result,'backup':backup}))
 finally:db.close()
