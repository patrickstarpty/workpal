"""Authored SMART activity, transcripts and deliverables; no actual model execution.
Insert-only stable IDs, local-only guard and SQLite backup preserve user records.
"""
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid5, NAMESPACE_URL
from sqlalchemy import select
from workpal_backend.config import Settings
from workpal_backend.infrastructure.database import Database
from workpal_backend.auth.models import users
from workpal_backend.workspaces.models import workspaces, members
from workpal_backend.workspace_content.repository import get_record, list_records, put_record

ROOT=Path(__file__).resolve().parents[1]
PREFIX='smart-activity-v1-'
PROVENANCE={'provenance':'authored_demonstration','execution':'synthetic','scenario_version':3}
# Each scenario records its own input, work, review and next action.
SCENARIOS=[
 ('Inbox messages currently have no clear escalation owner.', 'Separate initial triage, incident escalation and response acceptance; keep the owner accountable for the final response.', 'Do not turn every incoming message into an urgent ticket. Define the escalation threshold before implementation.', 'Await the owner’s prioritization of inbox ownership; no implementation is scheduled.'),
 ('The relationship picker needs keyboard access on a narrow screen.', 'Outline focus order, search, selection, escape and return focus; retain visible relation names.', 'Include removal and empty results, not just adding a relationship. Avoid relying on hover actions.', 'Await design capacity and the agreed interaction scope before starting.'),
 ('A disconnected upload should resume without losing the selected file.', 'Bound the work to retryable interruptions, retained upload identity and visible recovery controls.', 'Define when a file must be reselected and when recovery is impossible. Do not promise resume after every error.', 'Prioritize the upload recovery scope before planning implementation.'),
 ('Existing workspace switching behavior and draft ownership are available for review.', 'Prepare cases for switching A → B → A, refresh, sign-out and revoked membership.', 'Use two distinct drafts; a single draft cannot expose cross-workspace leakage.', 'QA Engineer can start from the supplied behavior; no design ticket is required.'),
 ('The attachment change needs a release owner and rollback path.', 'Prepare gates for accepted scope, verification, release approval and rollback ownership.', 'A completed agent run is not release permission. Keep the owner decision separate.', 'Release Engineer should collect the accepted build and verification input before scheduling release.'),
 ('Role profiles contain pinned source revisions.', 'List source URLs, pinned revisions, owners and proposed review order.', 'Keep current revisions in place until an upstream diff is reviewed. Source drift alone does not authorize replacement.', 'Reliability Engineer should compare the next available upstream revision.'),
 ('Uploads can be interrupted after the server has accepted part of the file.', 'Keep one upload identity across retries. Preserve the user’s selected file and show a resumable interruption state.', 'The first recovery draft conflated authentication failure with a retryable network interruption. Separate those states and return implementation for correction.', 'Continue implementation on this ticket. Consume the scoped interaction work in SMART-8; request SMART-10 regression review before SMART-17 release.'),
 ('SMART-7 needs a scoped recovery interaction with clear retry and reselect actions.', 'Draft separate states for connection loss, expired authorization and an unavailable local file.', 'Add focus restoration after retry and announce progress without repeatedly interrupting assistive technology.', 'Revise the recovery interaction and hand its accepted version to SMART-7; this ticket ends at design acceptance.'),
 ('Existing ticket links must preserve workspace ownership.', 'Resolve related ticket IDs inside the active workspace and retain a return path to the source ticket.', 'Reject cross-workspace references before rendering linked private content. A readable title is not sufficient authorization.', 'Finish the relationship navigation change, then request boundary and keyboard review.'),
 ('SMART-7 recovery behavior is ready for focused regression review.', 'Prepare a regression matrix for reconnect, repeated interruption, authorization expiry and retry cancellation.', 'Revision 1 missed cancellation during reconnect. Revision 2 adds that boundary and keeps an explicit expected outcome for each case.', 'Owner should review the regression matrix. Do not treat this review as permission to deploy SMART-17.'),
 ('The workspace release package contains a proposed change list and rollback notes.', 'Separate approval of the package from execution of the release; name the rollback owner.', 'The first checklist lacked an owner for rollback verification. Revision 2 adds the receiving owner and recovery acceptance criteria.', 'Await the workspace owner’s readiness decision; release execution remains a separate action.'),
 ('The maintenance guide must identify routine and incident escalation ownership.', 'Document source drift review, broken-reference escalation and how follow-up work returns to planning.', 'Avoid a circular handoff with no accepting owner. Revision 2 identifies the receiving role and expected input.', 'Owner should accept the revised escalation guide or return specific gaps.'),
 ('Recovery scope must distinguish retryable interruptions from unrecoverable failures.', 'Define recovery boundaries, acceptance criteria and explicit exclusions for the attachment work.', 'Keep authentication recovery and unavailable-file handling visible in the scope rather than hiding them as implementation details.', 'Scope accepted. The downstream delivery ticket can reference this decision without requiring a new planning ticket.'),
 ('Empty inbox views need guidance for both no messages and no filter matches.', 'Specify the empty state, filter-reset action and keyboard focus behavior.', 'Keep “no messages” distinct from “no matches.” The latter must preserve a clear way to reset filters.', 'Design accepted. Close the design scope; implementation can start independently with this artifact.'),
 ('Ticket titles must remain understandable and operable with keyboard navigation.', 'Carry title behavior through scope, design, implementation and verification in this ticket.', 'Avoid duplicate accessible names for the same title. Review both editing and reading states before acceptance.', 'The scoped delivery is accepted. Keep the phase decisions and reviewed handoff on this same ticket.'),
 ('Storage recovery verification requires an external test environment.', 'Prepare the recovery matrix and attempt to obtain the required isolated environment.', 'The environment is unavailable. Do not convert an access failure into a passing verification result.', 'Wait for the environment owner to restore access, then resume the saved matrix; verification remains blocked.'),
 ('SMART-7 recovery work needs release approval after SMART-10 review.', 'Prepare the proposed release checklist and rollback materials without executing the release.', 'Release is blocked on accepted implementation, completed regression review and explicit owner approval.', 'Resume only when SMART-7 and SMART-10 are accepted and the release owner authorizes the change.'),
 ('The pinned upstream source cannot be accessed with the available account.', 'Identify the unavailable repository reference and preserve the current pinned revision.', 'Do not replace a source with an unreviewed mirror or infer its contents from a title.', 'Ask the repository owner for access or an approved source snapshot; keep the investigation blocked.'),
 ('A proposal would split tickets automatically at each stage transition.', 'Compare automatic splitting with keeping one accountable outcome across phases.', 'Automatic phase-based splitting loses the original acceptance scope and creates work without an independent outcome.', 'Owner declined the proposal. Future splits require independently trackable scope.'),
 ('A proposal would require every ticket to start at planning.', 'Evaluate independent design, test and release work that already has accepted inputs.', 'Mandatory phase gates would prevent valid work from starting with supplied materials.', 'Owner declined mandatory gates. Allow tickets to begin at any stage.'),
 ('A proposal would close a ticket whenever an agent run completes.', 'Compare run completion, review acceptance and ticket completion criteria.', 'A successful run may still require corrections, another phase or an owner decision.', 'Owner declined automatic closure. Run results remain separate from ticket status.'),
]
ROLES={'plan':('intent','researcher'),'design':('design-role','adversarial'),'build':('implementation','pr-review'),'test':('verifier','review-fixes'),'deploy':('pipeline','security'),'maintain':('monitoring','oncall')}

RESPONSES={
10: """## Regression matrix
| Case | Setup / action | Expected outcome | Review state |
| --- | --- | --- | --- |
| Reconnect | Interrupt an upload after a partial acknowledgement, then reconnect | Resume the same upload identity; do not duplicate acknowledged data | Awaiting owner review |
| Repeated interruption | Disconnect again during a resumed transfer | Preserve progress and offer another retry | Awaiting owner review |
| Authorization expiry | Expire authorization before retry | Request authorization; do not loop automatic retries | Awaiting owner review |
| Cancel during reconnect | Cancel while a reconnect is pending | Stop retry scheduling and preserve an explicit cancelled state | Added in v2; awaiting owner review |

## Review response
Added the missing cancel-during-reconnect boundary with a distinct expected outcome. This matrix specifies acceptance behavior; it is not a measured execution report.""",
11: """## Release readiness checklist
- Scope: attach the accepted change list before release approval.
- Verification: link the accepted regression review and unresolved findings.
- Decision owner: workspace owner authorizes release separately from readiness review.
- Release owner: Release Engineer prepares the release and retains the preceding configuration.
- Rollback owner: Reliability Engineer checks restored configuration, workspace access and attachment availability.
- Stop condition: an unresolved acceptance blocker keeps release closed.

## Rollback handoff
Release Engineer supplies the preceding configuration reference and change list. Reliability Engineer confirms restored access and attachment availability before the owner closes recovery.

## Review response
Added rollback verification ownership and explicit recovery acceptance criteria. Awaiting the owner's readiness decision; no deployment is recorded.""",
12: """## Escalation ownership
| Trigger | First owner | Receiving owner | Required handoff |
| --- | --- | --- | --- |
| Pinned source changes | Reliability Engineer | Product Strategist | Revision diff, affected roles, proposed scope |
| Broken critical reference | Reliability Engineer | Incident Commander | Reference, affected work, reproduction context |
| Review finding needs repair | QA Engineer | Implementation Engineer | Finding, expected behavior, accepted input |

## Receiving gate
The receiving owner acknowledges scope before work transfers. If no owner accepts, the existing owner retains accountability and escalates to the workspace owner.

## Review response
Replaced the circular handoff with a named receiver and required input. Awaiting owner acceptance of this guide.""",
13: """## Accepted scope
- Resume retryable network interruptions using the existing upload identity.
- Preserve acknowledged progress and the selected local file while available.
- Show authorization expiry separately from a retryable interruption.
- Require file reselection when the local file is no longer available.

## Exclusions
No guarantee of recovery after loss of the local file; no silent overwrite of an accepted upload; no automatic production release.

## Acceptance boundaries
A retry does not duplicate acknowledged content. Cancelling prevents later retries. Authorization errors request user action.

## Review response
Authentication and unavailable-file handling are explicit scope boundaries. The owner accepts this planning outcome; delivery work remains independently tracked.""",
14: """## Accepted empty states
| Condition | Heading | Guidance | Action |
| --- | --- | --- | --- |
| Inbox has no messages | You're all caught up | New work will appear here. | No mandatory action |
| Filters exclude every message | No matching messages | Try changing your filters. | Clear filters |

## Keyboard behavior
Clear filters is reachable by Tab and activated by Enter or Space. Reset keeps focus on the filter control and announces the updated results. Empty states do not steal focus.

## Review response
Separated an empty inbox from an empty filtered result and defined a keyboard-operable reset. Design scope accepted; implementation is not implied.""",
15: """## Accepted title behavior
- Reading state exposes one accessible ticket title.
- Editing state has a labelled text input and explicit save/cancel actions.
- Save retains the new title and returns focus to the title control.
- Cancel retains the previous title and returns focus to the same control.
- Narrow layouts wrap titles without clipping the edit action.

## Review checklist
Check reading and editing names separately; check focus after save and cancel; verify wrapped text leaves controls reachable.

## Review response
Removed the proposed duplicate reading label and separated the input label from the displayed title. The owner acceptance concerns this scoped delivery record; no production deployment or measured test result is asserted.""",
}


def seed(session):
 ws=session.execute(select(workspaces).where(workspaces.c.slug=='workpal-team')).mappings().one();wid=ws['id']
 owner=session.execute(select(users).where(users.c.email=='workpal@fwd.com')).mappings().one()
 membership=session.execute(select(members).where(members.c.workspace_id==wid,members.c.user_id==owner['id'])).mappings().one()
 if membership['role'] not in ('owner','admin'):raise RuntimeError('Workspace owner required')
 def insert(kind,row):
  old=get_record(session,wid,kind,row['id'])
  if old is None:put_record(session,wid,kind,{**row,'workspace_id':wid,'_fixture':PROVENANCE})
  return old or {**row,'workspace_id':wid,'_fixture':PROVENANCE}
 # Register the same source-backed role identities in SMART without sharing mutable workspace records.
 roles=json.loads((ROOT/'apps/web/app/capabilities/data/role-profiles.json').read_text())
 for role in roles:
  insert('agents',dict(id='workflow-'+role['id'],name=role['name'],role=role['name'],description=role['mission'],
   instructions=role['mission']+'\n\nSource: '+role['sourceUrl'],owner_id=owner['id'],status='offline',runtime_id=None,
   runtime_bound=False,runtime_availability='offline',runtime_config={},custom_args=[],model='',permission_mode='public',
   invocation_targets=[],max_concurrent_tasks=1,conversation_starters=[],skills=[],avatar_url=role['avatarUrl'],archived_at=None,
   metadata={'source_author':role['sourceAuthor'],'source_url':role['sourceUrl'],'catalog_role_id':role['id']}))
 for index,scenario in enumerate(SCENARIOS,1):
  issue=get_record(session,wid,'issues',f'workflow-work-{index:02d}')
  if not issue or issue.get('_fixture',{}).get('scenario_version')!=2:raise RuntimeError('Expected authored SMART ticket')
  iid=issue['id'];status=issue['status'];stage=issue['metadata']['workflow_stage'];lead,peer=ROLES[stage]
  context,work,review,next_action=scenario
  base=datetime.fromisoformat(issue['created_at'].replace('Z','+00:00'))
  tick=0
  def stamp():
   nonlocal tick
   tick+=1
   return (base+timedelta(seconds=tick)).isoformat().replace('+00:00','Z')
  def event(key,action,details,role=None):
   insert('activities',dict(id=PREFIX+iid+'-'+key,issue_id=iid,type='activity',actor_type='agent' if role else 'member',
    actor_id='workflow-'+role if role else owner['id'],action=action,details=details,created_at=stamp()))
  def comment(key,heading,body,role=None,task=None,attachments=None):
   at=stamp()
   insert('comments',dict(id=PREFIX+iid+'-'+key,issue_id=iid,type='comment',author_type='agent' if role else 'member',
    author_id='workflow-'+role if role else owner['id'],content='## '+heading+'\n\n'+body,created_at=at,updated_at=at,
    revision=1,reactions=[],attachments=attachments or [],parent_id=None,**({'source_task_id':task} if task else {})))
  def run(key,role,summary,result,failed=False,retry_of=None):
   rid=str(uuid5(NAMESPACE_URL,PREFIX+iid+key));created=stamp();started=stamp()
   messages=[('text',{'content':summary}),('tool_use',{'tool':'Read','call_id':rid+'-read','input':{'file_path':iid+'/accepted-input.md'}}),
    ('tool_result',{'tool':'Read','call_id':rid+'-read','output':context,'output_truncated':False}),
    ('text',{'content':work}),('error' if failed else 'text',{'content':result})]
   for seq,(kind,body) in enumerate(messages,1):insert('task_messages',dict(id=rid+'-'+str(seq),task_id=rid,issue_id=iid,seq=seq,type=kind,created_at=stamp(),**body))
   completed=stamp()
   insert('task_runs',dict(id=rid,issue_id=iid,issue_identifier=issue['identifier'],issue_title=issue['title'],agent_id='workflow-'+role,
    runtime_id='',status='failed' if failed else 'completed',priority=0,created_at=created,dispatched_at=started,started_at=started,
    completed_at=completed,result=None if failed else {'summary':result},error=result if failed else None,trigger_summary=summary,
    attempt=2 if retry_of else 1,kind='issue',**({'parent_task_id':retry_of} if retry_of else {}),
    attribution={'source':'direct_assignment','precise':True,'initiator':{'id':owner['id'],'name':owner.get('name') or 'Workspace owner','email':owner['email']},**({'retry_of_task_id':retry_of} if retry_of else {})}))
   event('run-'+key,'task_failed' if failed else 'task_completed',{'task_id':rid},role)
   return rid
  def artifact(version,body,role=None,task=None):
   aid=PREFIX+iid+'-artifact-'+str(version);cid=PREFIX+iid+'-deliverable-'+str(version);at=stamp()
   text=f"# {issue['identifier']} — {issue['title']}\n\nRevision: {version}\n\n{body}\n"
   url=f'/delivery/smart/{iid}/{version}/work-record.md'
   attachment=insert('attachments',dict(id=aid,issue_id=iid,comment_id=cid,chat_session_id=None,chat_message_id=None,
    uploader_type='agent' if role else 'member',uploader_id='workflow-'+role if role else owner['id'],filename='work-record.md',
    url=url,download_url=url,markdown_url=url,content_type='text/markdown',size_bytes=len(text.encode()),created_at=at,
    comment_author_type='agent' if role else 'member',comment_author_id='workflow-'+role if role else owner['id'],comment_created_at=at))
   stored=insert('attachment_contents',{'id':aid,'text':text})
   # The database is authoritative; publishing uses the preserved revision content.
   files[url.lstrip('/')]=stored['text']
   comment('deliverable-'+str(version),'Work record · v'+str(version),body,role,task,[attachment])
  event('created','created',{})
  event('owner','assignee_changed',{'to_type':issue['assignee_type'],'to_id':issue['assignee_id']})
  comment('brief','Requested outcome',issue['title']+'\n\n**Input:** '+context+'\n\n**Acceptance:** '+issue['metadata']['completion_criteria'])
  comment('approach','Scope and approach',work,lead)
  comment('review-input','Review focus',review,peer)
  artifact(1,'## Input\n'+context+'\n\n## Proposed work\n'+work+'\n\n## Acceptance\n'+issue['metadata']['completion_criteria'],lead)
  if status not in ('backlog','todo'):
   event('started','status_changed',{'from':'todo','to':'in_progress'},lead)
   if index in (7,15):
    for phase,role,body in [('plan','intent','Scope and completion criteria recorded on this ticket.'),('design','design-role','Interaction constraints reviewed; implementation remains under the same outcome.')]:
     task=run(phase,role,phase.title()+' the delivery outcome',body)
     comment(phase+'-decision',phase.title()+' decision',body,role,task)
   failed=None
   if index==7:
    failed=run('attempt-1','implementation','Implement upload recovery — attempt 1','Provider rate limit interrupted the attempt before a deliverable was produced.',True)
    comment('retry','Retry decision','Retain the failed attempt. Retry implementation from the same accepted input without duplicating this ticket.')
    lead,peer='implementation','pr-review'
   task=run('work',lead,'Work on '+issue['title'],work,retry_of=failed)
   comment('progress','Work update',work,lead,task)
   reviewer=run('review',peer,'Review '+issue['title'],review)
   comment('findings','Review findings',review,peer,reviewer)
   if status in ('done','in_review'):
    task=run('revision',lead,'Address the review for '+issue['title'],RESPONSES[index])
    artifact(2,RESPONSES[index]+'\n\n## Decision / remaining gate\n'+next_action,lead,task)
    event('review-ready','status_changed',{'from':'in_progress','to':'in_review'},lead)
   if index==15:
    task=run('verify','verifier','Review title behavior against acceptance criteria','Review reading and editing states, duplicate accessible names and keyboard return focus.')
    comment('verification','Verification review','Reading and editing behavior reviewed against the scoped acceptance criteria. The owner still decides ticket completion.','verifier',task)
    comment('release','Delivery handoff','The owner accepted the scoped change and retained the reviewed work record with this ticket. No separate phase ticket is required.')
  decision={'backlog':'Prioritization decision','todo':'Ready to start','in_progress':'Continue work','in_review':'Review requested','done':'Owner acceptance','blocked':'Blocked on dependency','cancelled':'Owner decision'}[status]
  comment('decision',decision,next_action,None)
  if status not in ('in_review','in_progress'):event('current-status','status_changed',{'from':'in_review' if status=='done' else 'in_progress' if status not in ('todo','backlog') else 'backlog' if status=='todo' else None,'to':status})
  comment('next','Next action',next_action+'\n\n**Accountable owner:** '+(owner.get('name') or 'Workspace owner')+'.',lead)
  if index in (7,8,10,17):
   related={7:[8,10,17],8:[7],10:[7,17],17:[7,10]}[index]
   comment('related','Related work','\n'.join(f'- [SMART-{n}](#/workpal-team/issues/workflow-work-{n:02d})' for n in related)+'\n\nHandoff carries accepted scope and the reviewed revision; it does not automatically close either ticket.',lead)
 return {kind:sum(r['id'].startswith(PREFIX) if kind not in ('task_runs','task_messages') else r.get('_fixture',{}).get('scenario_version')==3 for r in list_records(session,wid,kind)) for kind in ('comments','activities','task_runs','task_messages','attachments')}

files={}
def main():
 settings=Settings()
 if not settings.dev_auth:raise RuntimeError('Local development authentication required')
 db=Database(settings)
 try:
  backup=str(db.engine.url.database)+'.before-smart-activity-'+datetime.now().strftime('%Y%m%d%H%M%S%f')
  with sqlite3.connect(db.engine.url.database) as source,sqlite3.connect(backup) as target:source.backup(target)
  with db.transaction() as session:result=seed(session)
  for relative,content in files.items():
   path=ROOT/'apps/web/public'/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content)
  print(json.dumps({**result,'backup':backup}))
 finally:db.close()
if __name__=='__main__':main()
