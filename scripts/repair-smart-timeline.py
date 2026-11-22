"""Repair only user-authorized authored SMART history. No execution or acceptance is generated.
Dry-run by default; --apply requires local dev auth, backs up SQLite, and commits atomically.
Actual evidence, uploaded bytes, user comments and non-target tickets stay unchanged.
"""
import argparse, copy, hashlib, json, sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from sqlalchemy import select
from workpal_backend.config import Settings
from workpal_backend.infrastructure.database import Database
from workpal_backend.workspaces.models import workspaces
from workpal_backend.workspace_content import repository as repo

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/handoffs/smart-timeline'
PREFIX='smart-activity-v1-'
VERSION='lifecycle-order-v1'
# Minutes from the existing issue creation. Comments have human reading/decision gaps;
# execution envelopes have their own durations. No durations are claimed as measurements.
COMMON={'created':0.1,'owner':0.5,'brief':2,'approach':5}
SCHEDULES={
2:{'deliverable-1':15,'review-input':20,'decision':25,'current-status':25.2,'next':28},
7:{'started':5.5,'deliverable-1':8,'plan-decision':15,'design-decision':28,'retry':33,
   'progress':53,'review-input':56,'findings':65,'decision':69,'next':73,'related':76},
8:{'started':5.5,'deliverable-1':8,'progress':23,'review-input':27,'findings':35,'decision':39,'next':43,'related':46},
14:{'started':5.5,'deliverable-1':8,'progress':22,'review-input':26,'findings':34,
    'deliverable-2':46,'review-ready':46.2,'decision':52,'current-status':52.2,'next':56},
15:{'started':5.5,'deliverable-1':8,'plan-decision':14,'design-decision':26,'progress':43,
    'review-input':46,'findings':54,'deliverable-2':65,'review-ready':65.2,
    'verification':73,'decision':76,'current-status':76.2,'release':78,'next':80},
20:{'started':5.5,'deliverable-1':8,'progress':24,'review-input':28,'findings':37,
    'decision':42,'current-status':42.2,'next':46},
}
RUNS={
2:{},7:{'plan':(6,13),'design':(16,26),'attempt-1':(29,31),'work':(35,51),'review':(57,63)},
8:{'work':(9,21),'review':(28,33)},
14:{'work':(9,20),'review':(27,32),'revision':(36,44)},
15:{'plan':(6,12),'design':(15,24),'work':(28,41),'review':(47,52),'revision':(56,63),'verify':(66,71)},
20:{'work':(9,22),'review':(29,35)},
}
TDS={2:'deliverable-1',7:'design-decision',8:'progress',14:'progress',15:'design-decision',20:'progress'}
# Wording names inputs and pending decisions; it does not add code, test, PR or approval claims.
COPY={
2:{'approach':('Design scope','Cover opening the relationship picker, searching accessible tickets, adding/removing a link and returning focus. Keep no-results and save-failure behavior in the same specification.'),
   'review-input':('Design review focus','Review FDS-SMART-2 v1.0: check removal with the keyboard, focus after Escape, empty search results and revoked workspace access. These are review questions, not verified browser results.'),
   'decision':('Prioritization decision','Keep the ticket in backlog. The attached design is a proposal for scoping; implementation and final design acceptance are not scheduled.'),
   'next':('Next action','The owner should prioritize the proposed keyboard scope. Then resolve the design review questions before assigning implementation.')},
7:{'approach':('Recovery scope','Separate network interruption, expired authorization and missing local bytes. Preserve file identity when possible; byte-offset continuation requires an explicit backend capability.'),
   'plan-decision':('Plan decision','Keep recovery, cancellation and workspace ownership in one delivery scope. A successful retry must not create duplicate attachments. Backend continuation support is a dependency, not an assumption.'),
   'design-decision':('Functional design · FDS v1.0','FDS-SMART-7 defines retry serialization, stale-callback handling and attachment finalization. Use Restart when continuation is unsupported. SMART-8 owns the detailed interaction feedback; its acceptance remains a downstream input.'),
   'progress':('Implementation handoff','Use FDS-SMART-7 v1.0 as the implementation baseline. Review retry identity, authorization handling and cancellation separately. A ticket-specific commit or PR is still required to substantiate the implementation handoff.'),
   'review-input':('Code review scope','Check the implementation against the recovery design: retryable connection failure must not share the authorization-expiry path; cancelling must invalidate queued retries. Record the scoped patch before treating these checks as completed code review.'),
   'findings':('Review findings · correction required','The recovery work record does not separate authorization failure from retryable connection interruption. Return that distinction for correction and link the affected code in the next submission. No corrected patch or passing recheck is attached.'),
   'next':('Next action','Implementation Engineer should supply the scoped patch and address the recovery-state finding. Request a recheck of that revision before SMART-10 regression acceptance or SMART-17 release approval.')},
8:{'progress':('Functional design · FDS v1.0','FDS-SMART-8 separates Retry upload, Sign in to continue and Choose file. Cancellation invalidates queued retries; continuation is offered only when supported. Please review focus restoration and progress announcements before handoff to SMART-7.'),
   'review-input':('Design review scope','Review the submitted recovery interaction, especially keyboard focus after Retry and status announcements during repeated interruptions.'),
   'findings':('Design review · changes requested','The recovery states are specified, but the return-focus target after retry and the announcement cadence need explicit acceptance wording. Revise those sections before the design is accepted for SMART-7.'),
   'next':('Next action','Revise the focus and announcement requirements and submit a new TDS revision for review. Keep v1.0 attached to its original activity; SMART-7 must not treat the pending revision as accepted.')},
14:{'progress':('Functional design · FDS v1.0','FDS-SMART-14 distinguishes an empty inbox from zero filter matches. Clear filters preserves the workspace; loading and request failure have separate states. Review the reset action and resulting focus before accepting the design.'),
    'review-input':('Design review scope','Compare the no-messages and no-matches cases in FDS-SMART-14. Check that Clear filters resets only inbox filters and remains keyboard accessible.'),
    'findings':('Design review findings','Keep the two empty headings distinct. The revision response should explicitly state what Clear filters changes and how the keyboard user continues after reset.')},
15:{'approach':('Title scope','Cover the reading state, labelled editing, Save/Cancel, validation and focus return. Keep remote-update conflicts and narrow-width wrapping in the design; do not expand this ticket into a general editor redesign.'),
    'plan-decision':('Plan decision','Use one accessible title in reading mode and a labelled input in editing mode. Acceptance must cover Save, Cancel, empty input and focus restoration, with browser evidence still required.'),
    'design-decision':('Functional design · FDS v1.0','FDS-SMART-15 defines read/edit states, explicit Save/Cancel, failed-save draft preservation and remote-update reconciliation. Use its FR identifiers for the implementation review and subsequent verification.'),
    'progress':('Implementation handoff','Review title-editor behavior against FDS-SMART-15 v1.0. The scoped commit or PR must identify accessible naming and focus changes; the attached work record alone is not a code diff.'),
    'review-input':('Code review scope','Check reading and editing states for duplicate accessible names. Review Save/Cancel focus return against the design, then identify the affected diff and tests before acceptance.'),
    'findings':('Review findings','The title work record needs one explicit accessible-name rule across reading and editing states. The response must also name the focus target after Save and Cancel; verification of the real editor is still needed.'),
    'verification':('Verification review','The revised work record describes one accessible title and focus return. Verify those expectations against the real editor and retain actual results separately; a document review does not establish browser accessibility acceptance.')},
20:{'progress':('Alternative design · FDS v1.0','The attached FDS-SMART-20 describes flexible stage entry as an alternative to mandatory gates. A test ticket can begin with an existing build; release work can begin with an accepted package. Stage choice does not imply acceptance or close the ticket.'),
    'review-input':('Design review scope','Compare mandatory Plan-first gates with the flexible-entry alternative. Check independent test and release requests with existing inputs, and missing-input handling.'),
    'findings':('Design review findings','Mandatory Plan-first gates reject valid work that already has its required input. Keep the selected stage and request the specific missing evidence instead of forcing unrelated upstream tickets.'),
    'decision':('Proposal decision','Decline mandatory phase gates. Retain the flexible-entry TDS as the alternative design; this decision does not authorize implementation or mark that alternative as delivered.')},
}

def parse(v): return datetime.fromisoformat(v.replace('Z','+00:00'))
def iso(v): return v.isoformat(timespec='milliseconds').replace('+00:00','Z')
def digest(rows): return hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()

def repair(session):
 ws=session.execute(select(workspaces).where(workspaces.c.slug=='workpal-team')).mappings().one();wid=ws['id']
 kinds=('issues','comments','activities','task_runs','task_messages','attachments','delivery_revisions','delivery_reviews')
 rows={k:{r['id']:r for r in repo.list_records(session,wid,k)} for k in kinds}
 before=copy.deepcopy(rows);report=[]
 for n in SCHEDULES:
  iid=f'workflow-work-{n:02d}';prefix=PREFIX+iid+'-';issue=rows['issues'][iid];base=parse(issue['created_at'])
  stamp=lambda minutes:iso(base+timedelta(minutes=minutes))
  selected={k:[r for r in rows[k].values() if r.get('issue_id')==iid and r.get('_fixture',{}).get('execution')=='synthetic'] for k in kinds}
  schedule={**COMMON,**SCHEDULES[n]}
  for k in ('comments','activities'):
   for r in selected[k]:
    suffix=r['id'].removeprefix(prefix)
    if suffix.startswith('run-'):continue
    if suffix not in schedule:raise ValueError('Unscheduled '+r['id'])
    r.setdefault('_timeline_original',{'created_at':r['created_at'],'content':r.get('content')})
    if k=='comments' and r['_fixture'].get('timeline_revision')!=VERSION:r['updated_at']=iso(datetime.now(timezone.utc))
    r['created_at']=stamp(schedule[suffix]);r['_fixture']['timeline_revision']=VERSION
    phase='design'
    if n in (7,15):
     phase='plan' if schedule[suffix]<RUNS[n]['design'][0] else 'design' if schedule[suffix]<RUNS[n].get('attempt-1',RUNS[n]['work'])[0] else 'build'
     if n==15 and schedule[suffix]>=66:phase='test' if schedule[suffix]<76 else 'deploy'
    r['lifecycle_stage']=phase
    if n==7 and suffix=='review-input':r['author_id']='workflow-pr-review'
    if n==15 and suffix in ('approach','deliverable-1'):r['author_id']='workflow-intent'
    if n==15 and suffix=='started':r['actor_id']='workflow-intent'
    if k=='comments':
     if suffix in COPY.get(n,{}):heading,body=COPY[n][suffix];r['content']=f'## {heading}\n\n{body}'
     r['updated_at']=max(r.get('updated_at',r['created_at']),r['created_at'])
  for key,(start,end) in RUNS[n].items():
   event=rows['activities'][prefix+'run-'+key];run=rows['task_runs'][event['details']['task_id']]
   assert run in selected['task_runs']
   run.setdefault('_timeline_original',{f:run.get(f) for f in ('created_at','dispatched_at','started_at','completed_at')})
   run.update(created_at=stamp(start),dispatched_at=stamp(start+.1),started_at=stamp(start+.2),completed_at=stamp(end))
   run['_fixture']['timeline_revision']=VERSION
   phase=key if key in ('plan','design') else 'test' if key=='verify' else 'build' if n in (7,15) else 'design'
   run['lifecycle_stage']=phase;event['lifecycle_stage']=phase
   event.setdefault('_timeline_original',{'created_at':event['created_at']});event['created_at']=stamp(end+.1)
   event['_fixture']['timeline_revision']=VERSION
   messages=sorted([m for m in selected['task_messages'] if m['task_id']==run['id']],key=lambda m:m['seq'])
   for i,m in enumerate(messages):
    m.setdefault('_timeline_original',{'created_at':m['created_at']})
    m['created_at']=stamp(start+.3+(end-start-.4)*(i+1)/(len(messages)+1));m['_fixture']['timeline_revision']=VERSION
  # Move the existing DOCX, keeping bytes, hash, revision and actual upload timestamp.
  aid=f'smart-tds-v1-{n}';attachment=rows['attachments'][aid];target=rows['comments'][prefix+TDS[n]]
  attachment.setdefault('_timeline_original',copy.deepcopy(attachment))
  attachment.setdefault('uploaded_at',attachment['created_at'])
  attachment.update(comment_id=target['id'],source_task_id=target.get('source_task_id'),
                    comment_created_at=target['created_at'],comment_author_type=target['author_type'],comment_author_id=target['author_id'],
                    lifecycle_stage='design')
  # created_at remains the real upload time; origin activity time is a separate field.
  for c in rows['comments'].values():
   if c.get('issue_id')==iid and c['id'].startswith(prefix):c['attachments']=[a for a in c.get('attachments',[]) if a['id']!=aid]
  target['attachments'].append(copy.deepcopy(attachment))
  for a in selected['attachments']:
   c=rows['comments'][a['comment_id']]
   a.setdefault('_timeline_original',{'created_at':a['created_at'],'comment_created_at':a.get('comment_created_at')})
   a.update(created_at=c['created_at'],comment_created_at=c['created_at'],uploader_id=c['author_id'],comment_author_id=c['author_id']);a['_fixture']['timeline_revision']=VERSION
   c['attachments']=[copy.deepcopy(a) if old['id']==a['id'] else old for old in c.get('attachments',[])]
  comments=sorted(selected['comments'],key=lambda r:parse(r['created_at']))
  assert all(parse(c['created_at'])>=base for c in comments)
  for c in comments:
   if c.get('source_task_id'):assert parse(rows['task_runs'][c['source_task_id']]['completed_at'])<=parse(c['created_at']),c['id']
  for run in selected['task_runs']:
   assert parse(run['created_at'])<parse(run['started_at'])<parse(run['completed_at'])
   for m in selected['task_messages']:
    if m['task_id']==run['id']:assert parse(run['started_at'])<parse(m['created_at'])<parse(run['completed_at'])
  assert parse(target['created_at'])<parse(rows['comments'][prefix+'review-input']['created_at'])
  if n in (7,15):assert parse(target['created_at'])<parse(rows['task_runs'][rows['activities'][prefix+'run-work']['details']['task_id']]['started_at'])
  if n==14:assert parse(target['created_at'])<parse(rows['comments'][prefix+'findings']['created_at'])<parse(rows['comments'][prefix+'deliverable-2']['created_at'])
  external=[r for k in ('comments','activities') for r in rows[k].values() if r.get('issue_id')==iid and not r.get('_fixture')]
  assert max(parse(c['created_at']) for c in comments)<min(parse(r['created_at']) for r in external)
  report.append({'ticket':f'SMART-{n}','tds_activity':target['id'],'tds_uploaded_at':attachment['uploaded_at'],
                 'activities':[{'id':c['id'],'at':c['created_at'],'stage':c['lifecycle_stage'],'heading':c['content'].splitlines()[0]} for c in comments]})
 changes=[]
 for k in kinds:
  for rid,r in rows[k].items():
   old=before[k][rid]
   if old==r:continue
   assert k not in ('issues','delivery_revisions','delivery_reviews')
   assert old.get('_fixture',{}).get('execution')=='synthetic' or rid.startswith('smart-tds-v1-')
   repo.put_record(session,wid,k,r);changes.append({'kind':k,'id':rid})
 return {'revision':VERSION,'changes':changes,'tickets':report,'unchanged_real_evidence':digest(before['delivery_revisions'])==digest(rows['delivery_revisions'])}

def main():
 args=argparse.ArgumentParser();args.add_argument('--apply',action='store_true');args=args.parse_args()
 settings=Settings();assert settings.dev_auth,'Local development only'
 db=Database(settings);OUT.mkdir(parents=True,exist_ok=True)
 try:
  backup=None
  if args.apply:
   backup=str(db.engine.url.database)+'.before-timeline-'+datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
   with sqlite3.connect(db.engine.url.database) as src,sqlite3.connect(backup) as dst:src.backup(dst)
  with db.transaction() as session:
   result=repair(session)
   if not args.apply:session.rollback()
  result.update(applied=args.apply,backup=backup)
  if args.apply:(OUT/('change-'+datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')+'.json')).write_text(json.dumps(result,indent=2)+'\n')
  (OUT/('applied.json' if args.apply else 'preview.json')).write_text(json.dumps(result,indent=2)+'\n')
  print(json.dumps({'applied':args.apply,'changed_records':len(result['changes']),'tickets':len(result['tickets']),'backup':backup,'unchanged_real_evidence':result['unchanged_real_evidence']}))
 finally:db.close()
if __name__=='__main__':main()
