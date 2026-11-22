"""Insert authored workflow examples into a new SMART workspace; never run agents.
Existing records (including edits to these examples) are never overwritten.
"""
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import select, update
from workpal_backend.config import Settings
from workpal_backend.infrastructure.database import Database
from workpal_backend.auth.models import users
from workpal_backend.workspaces.models import workspaces, members
from workpal_backend.workspaces.service import create_workspace
from workpal_backend.workspace_content.repository import get_record, put_record, list_records

SLUG = 'workpal-team'  # workpal itself is a reserved application route.
PROJECT = 'flexible-workflow'
STAGES = ['plan', 'design', 'build', 'test', 'deploy', 'maintain']
STATUSES = ['backlog', 'todo', 'in_progress', 'in_review', 'done', 'blocked', 'cancelled']
# Title, completion criterion. Status describes the authored scenario, not real execution.
WORK = [
 ('Define shared inbox ownership', 'Agree who owns triage, escalation and response acceptance.'),
 ('Design keyboard navigation for ticket relationships', 'Accept a keyboard-accessible relationship picker with narrow-screen layouts.'),
 ('Add resumable attachment uploads', 'Accept implementation, recovery tests and release review for interrupted uploads.'),
 ('Verify workspace switching preserves drafts', 'Review a test report covering draft isolation and workspace switching.'),
 ('Prepare the attachment release checklist', 'Approve release scope, rollback steps and the release owner.'),
 ('Review source revision drift', 'Record changed sources and open scoped follow-up work where needed.'),
 ('Deliver upload interruption recovery', 'Accept the recovery interaction, implementation, regression checks and release decision.'),
 ('Design upload recovery interactions', 'Accept recovery states, retry copy and keyboard behavior; implementation is separate.'),
 ('Implement ticket relationship navigation', 'Accept navigable related tickets with workspace boundaries preserved.'),
 ('Review upload retry regression coverage', 'Accept coverage for repeated failures, refreshes and retry cancellation.'),
 ('Review workspace release readiness', 'Owner accepts the release checklist and rollback materials.'),
 ('Review the maintenance escalation guide', 'Accept named escalation ownership and links to follow-up work.'),
 ('Agree attachment recovery scope', 'Owner accepts the recovery scope and its explicit out-of-scope cases.'),
 ('Design empty inbox guidance', 'Owner accepts copy and layouts for empty and filtered inbox views.'),
 ('Deliver accessible ticket titles', 'Accept implementation and keyboard verification against the agreed title behavior.'),
 ('Verify external storage recovery', 'Finish verification after the storage test environment becomes available.'),
 ('Release upload recovery', 'Obtain the release owner decision after regression review; retain rollback instructions.'),
 ('Investigate missing source access', 'Resolve repository access before comparing pinned source revisions.'),
 ('Explore automatic ticket splitting', 'Close the proposal because independent scope, not stage transitions, determines splitting.'),
 ('Design mandatory phase gates', 'Close the proposal because work can start at any stage.'),
 ('Implement automatic closure after each run', 'Close the proposal because run completion does not satisfy ticket acceptance.'),
]


def register(session):
 owner = session.execute(select(users).where(users.c.email == 'workpal@fwd.com')).mappings().one()
 ws = session.execute(select(workspaces).where(workspaces.c.slug == SLUG)).mappings().one_or_none()
 if ws is None:
  ws = create_workspace(session, owner['id'], 'SMART', SLUG, 'SMART', 'Outcome-driven work across planning, design, delivery and maintenance.')
 else:
  member = session.execute(select(members).where(members.c.workspace_id == ws['id'], members.c.user_id == owner['id'])).mappings().one_or_none()
  if not member or member['role'] != 'owner' or not get_record(session, ws['id'], 'projects', PROJECT):
   raise RuntimeError('Existing workspace is not owned by this registration; refusing to modify it')
 wid = ws['id']
 stamp = datetime.now(timezone.utc).isoformat()
 base = dict(workspace_id=wid, created_at=stamp, updated_at=stamp, creator_id=owner['id'], creator_type='member',
             priority='medium', labels=[], metadata={}, properties={}, visibility='workspace', position=0,
             icon=None, lead_id=None, lead_type=None, start_date=None, due_date=None,
             _fixture={'provenance':'authored_demonstration','execution':'none','scenario_version':2})
 def insert(kind, body):
  if get_record(session,wid,kind,body['id']) is None:
   put_record(session,wid,kind,body)
 insert('projects',dict(base,id=PROJECT,title='Workflow work',name='Workflow work',status='in_progress',
  description='Tickets own outcomes. Stage describes the current activity; status describes progress. Start anywhere and split only independently scoped work.',issue_count=21,done_count=3))
 counter=max(ws.get('issue_counter',0),max((r.get('number',0) for r in list_records(session,wid,'issues')),default=0))
 for index,(title,criteria) in enumerate(WORK):
  iid=f'workflow-work-{index+1:02d}'
  if get_record(session,wid,'issues',iid): continue
  counter+=1
  stage=STAGES[index%6]; status=STATUSES[index//3]
  scope='Full delivery' if index in (2,6,14) else 'Scoped work'
  source = {7:6,9:6,16:6}.get(index)
  relationship = f'\n\n## Related work\n[Upload recovery](#/{SLUG}/issues/workflow-work-07) — '+('design handoff' if index==7 else 'verification input' if index==9 else 'release dependency') if source is not None else ''
  context = ('Existing upload requirements and recovery constraints.' if index in (2,6,7,9,16) else 'Owner-provided scope and relevant existing materials; no earlier stage is required.')
  description=f'## Goal\n{title}\n\n## Scope\n{scope}. '+('Keep planning, design, build, verification and release decisions on this ticket as work advances.' if scope=='Full delivery' else 'Complete when the scoped outcome is accepted; deployment is not an implicit requirement.')+f'\n\n## Current activity\n{stage.title()}\n\n## Input\n{context}\n\n## Completion criteria\n{criteria}'+relationship
  if status=='blocked': description+='\n\n## Waiting on\n'+criteria
  if status=='cancelled': description+='\n\n## Decision\n'+criteria
  if index==6: description+=f'\n\n## Work history\nScope agreed → recovery design reviewed → implementation in progress. Verification can return here for rework without opening a replacement ticket.\n\n## Related work\n[Recovery interaction](#/{SLUG}/issues/workflow-work-08) · [Regression review](#/{SLUG}/issues/workflow-work-10) · [Release](#/{SLUG}/issues/workflow-work-17)'
  insert('issues',dict(base,id=iid,number=counter,identifier=f"{ws['issue_prefix']}-{counter}",title=title,description=description,status=status,
    assignee_type='member',assignee_id=owner['id'],parent_issue_id=None,project_id=PROJECT,sub_issue_count=0,completed_sub_issue_count=0,
    metadata={'workflow_stage':stage,'work_scope':scope,'completion_criteria':criteria}))
 session.execute(update(workspaces).where(workspaces.c.id==wid).values(issue_counter=counter))
 rows=[r for r in list_records(session,wid,'issues') if r.get('project_id')==PROJECT]
 return {'workspace':SLUG,'issues':len(rows),'stages':dict(Counter((r.get('metadata') or {}).get('workflow_stage', 'unassigned') for r in rows)), 'statuses':dict(Counter(r['status'] for r in rows))}


def main():
 settings=Settings()
 if not settings.dev_auth: raise RuntimeError('Local development authentication required')
 db=Database(settings)
 try:
  backup=str(db.engine.url.database)+'.before-flexible-workflow-'+datetime.now().strftime('%Y%m%d%H%M%S%f')
  with sqlite3.connect(db.engine.url.database) as source,sqlite3.connect(backup) as target: source.backup(target)
  with db.transaction() as session: result=register(session)
  print(json.dumps({**result,'backup':backup}))
 finally: db.close()

if __name__=='__main__': main()
