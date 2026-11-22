"""Authored local demonstration fixtures, never evidence of actual agent execution.
Run after register-lifecycle.py using the local service environment. Stable IDs make
reruns idempotent; only this fixture namespace and the seven named issues change.
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
from workpal_backend.workspaces.models import workspaces
from workpal_backend.workspace_content.repository import get_record, put_record, list_records

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'story-v1-'
PROVENANCE = {'provenance': 'authored_demonstration', 'scenario_version': 1, 'execution': 'synthetic'}
STAGES = [
    dict(key='plan', name='Plan', role='intent', peer='researcher', squad='discovery', artifact='scope-brief',
         goal='Give every delivery role a clear responsibility and a traceable source workflow.',
         input='The team cannot tell who owns decisions, implementation, review or release. Define a single accountable owner for each stage.',
         work='Reviewed pstack, gstack, Matt Pocock skills and autoresearch. Separated reusable workflow methods from personality or endorsement claims.',
         review='Add an explicit acceptance criterion: every handoff names the receiving role, required input and exit gate. Keep author attribution in role profiles.',
         output='Scope v2 approved: 15 named roles, 5 squads, six delivery gates; every role has a pinned source. Human approval is required before release.',
         artifact_body='## Acceptance criteria\n- 15 role profiles with responsibilities and pinned source links.\n- Five squads with one accountable leader each.\n- Every delivery stage names an owner, input, output and review gate.\n- Agent completion requests human review; it does not authorize release.\n\n## Out of scope\nProduction credentials, billing and autonomous production changes.'),
    dict(key='design', name='Design', role='design-role', peer='adversarial', squad='discovery', artifact='architecture-decision',
         goal='Keep one stable identity for each role across the catalog, workspace and squad roster.',
         input='Accepted scope brief v2 from Plan; 15 roles, five squads and explicit human release ownership.',
         work='Mapped role IDs to workspace agents, source revisions and skill bindings. Designed a repeatable import with a database backup before mutation.',
         review='A renamed display label must not create a second agent. Keep the stable ID, preserve human edits and update only fixture-owned fields.',
         output='ADR v2 accepted: stable role IDs, workspace-scoped records, explicit squad leader, transactional imports and source revision tracking.',
         artifact_body='## Decision\nUse stable role IDs across the role catalog and workspace. Display names may change without changing identity.\n\n## Boundaries\nCatalog describes capability; workspace owns membership and task assignment. Runtime availability is independent of role identity.\n\n## Recovery\nBack up SQLite before imports. Validate every role and leader reference before commit.\n\n## Rejected option\nGenerating agent IDs from display names causes duplicate agents after renames.'),
    dict(key='build', name='Build', role='implementation', peer='pr-review', squad='delivery', artifact='implementation-report',
         goal='Register the role and squad catalog and connect the six-stage delivery route.',
         input='Approved architecture decision v2; stable role IDs and transactional registration contract.',
         work='Implemented role-to-agent mapping, source attribution and squad membership. Split navigation, roster import and reference validation into reviewable changes.',
         review='Found a leader mapping defect: the importer writes lead while the membership contract expects leader. Correct the mapping and verify that rerunning creates no duplicate memberships.',
         output='Implementation v2 ready: leader mapping corrected, 15 role references and five squad rosters resolve, and repeated registration preserves stable IDs.',
         artifact_body='## Change set\n- Source-backed role profiles and squad memberships.\n- Overview links to six delivery tickets.\n- Stable registration IDs and backup before write.\n\n## Review finding B-01\nMembership role `lead` was incompatible with `leader`. The second revision fixes the mapping and adds a roster consistency check.\n\n## Recovery from failed run\nAttempt 1 stopped on a provider rate limit before publishing changes. Attempt 2 resumed from the accepted design and completed implementation. Both transcripts are retained.'),
    dict(key='test', name='Test', role='verifier', peer='review-fixes', squad='assurance', artifact='test-report',
         goal='Verify that a user can follow the complete lifecycle without missing owners, references or artifacts.',
         input='Implementation report v2 and corrected squad leader mapping from Build.',
         work='Checked role references, roster ownership, repeated registration, parent-child links and the sign-in-to-delivery path. Opened finding Q-01 for a missing return link on the maintenance handoff.',
         review='Q-01 fixed: the maintenance handoff now links back to Plan and to the parent. Rechecked all six forward and return links against their issue IDs.',
         output='Verification v2 accepted: Q-01 closed; role, squad, ownership, delivery links and artifact revision checks all pass. Release gate is ready for the owner.',
         artifact_body='## Acceptance matrix\n| Check | Result | Evidence |\n| --- | --- | --- |\n| Role identity and source mapping | Pass | 15 role references resolved |\n| Squad leadership | Pass | Five squads, one leader each |\n| Repeat import | Pass | Stable IDs; no duplicate roster entries |\n| Delivery navigation | Pass | Six stages, parent and return links |\n| Artifact revisions | Pass | Prior revision retained |\n\n## Q-01\nMaintenance lacked a return link to Plan. Maintenance Engineer corrected it; QA Engineer verified the revised route.\n\n## Release recommendation\nProceed to human release review; no unresolved acceptance blockers.'),
    dict(key='deploy', name='Deploy', role='pipeline', peer='security', squad='operations', artifact='release-checklist',
         goal='Package the accepted workflow configuration and obtain explicit release approval.',
         input='Test report v2 with Q-01 closed and no remaining acceptance blockers.',
         work='Prepared a release checklist, rollback steps and ownership map. Security review checked that source references and deliverables contain no credentials.',
         review='Release review complete: retain the previous configuration snapshot, scope rollback to this release and hand monitoring ownership to Reliability Engineer.',
         output='Release package v2 approved by the workspace owner. Configuration published to the delivery workspace; rollback instructions and maintenance ownership acknowledged.',
         artifact_body='## Release gates\n- QA acceptance completed.\n- Security review completed.\n- Workspace owner approved release after reviewing v2.\n- Previous configuration snapshot retained.\n\n## Rollback\nPause edits, retain the current SQLite file, restore the pre-release snapshot and verify workspace membership and role references.\n\n## Handoff\nReliability Engineer owns source drift review, broken-reference checks and the next maintenance checkpoint.'),
    dict(key='maintain', name='Maintain', role='monitoring', peer='oncall', squad='operations', artifact='maintenance-handoff',
         goal='Close the release loop and keep the next source update owned and reviewable.',
         input='Approved release package v2, previous snapshot and named reliability owner.',
         work='Completed the initial post-release review of roster references and delivery navigation. Checked pinned source revisions and recorded a follow-up to compare future upstream changes.',
         review='No immediate intervention required. Preserve the current pinned revisions; bring changed upstream workflows back through Plan before updating roles.',
         output='Initial review complete. Maintenance remains in progress: the next source-drift review is assigned, with a return path to Plan and a defined escalation owner.',
         artifact_body='## Initial review\nRole and squad references resolve; ownership and delivery links are complete.\n\n## Ongoing checkpoint\nCompare pinned upstream revisions at the next source update. Capture the diff, affected roles and proposed validation in Plan before applying changes.\n\n## Escalation\nIncident Commander handles broken critical references; Reliability Engineer owns routine drift review.\n\n## Exit gate\nAn accepted source update has passed Plan, Design, Build and Test. Until then this maintenance ticket remains in progress.'),
]


def seed_story():
    settings = Settings()
    if not settings.dev_auth:
        raise RuntimeError('This fixture requires local development authentication')
    db = Database(settings)
    files = {}
    try:
        backup = str(db.engine.url.database) + '.before-story-' + datetime.now().strftime('%Y%m%d%H%M%S%f')
        with sqlite3.connect(db.engine.url.database) as source, sqlite3.connect(backup) as target:
            source.backup(target)
        with db.transaction() as session:
            owner = session.execute(select(users).where(users.c.email == 'workpal@fwd.com')).mappings().one()
            ws = session.execute(select(workspaces).where(workspaces.c.slug == 'review')).mappings().one()
            wid = ws['id']
            existing = {r['id']: r for r in list_records(session, wid, 'issues')}
            ids = {'lifecycle-delivery'} | {'lifecycle-' + s['key'] for s in STAGES}
            if set(existing) != ids:
                raise RuntimeError('Expected only the parent and six lifecycle tickets; refusing to alter other tickets')
            from workpal_backend.workspace_content.repository import delete_record
            for kind in ('task_runs', 'task_messages'):
                for old in list_records(session, wid, kind):
                    if old['id'].startswith(PREFIX):
                        delete_record(session, wid, kind, old['id'])
            base = datetime(2026, 11, 20, 1, tzinfo=timezone.utc)
            def stamp(minute):
                return (base + timedelta(minutes=minute)).isoformat().replace('+00:00', 'Z')
            def put(kind, row):
                return put_record(session, wid, kind, {**row, 'workspace_id': wid, 'metadata': {}, '_fixture': PROVENANCE})
            def comment(issue, suffix, minute, role, content, task=None, attachments=None):
                row = dict(id=PREFIX+issue+'-'+suffix, issue_id=issue, author_type='agent' if role else 'member',
                           author_id='workflow-'+role if role else owner['id'], content=content, type='comment',
                           created_at=stamp(minute), updated_at=stamp(minute), revision=1, reactions=[],
                           attachments=attachments or [], parent_id=None)
                if task: row['source_task_id'] = task
                return put('comments', row)
            def activity(issue, suffix, minute, role, action, details):
                return put('activities', dict(id=PREFIX+issue+'-'+suffix, issue_id=issue, type='activity',
                    actor_type='agent' if role else 'member', actor_id='workflow-'+role if role else owner['id'],
                    action=action, details=details, created_at=stamp(minute)))
            def run(issue, suffix, minute, role, summary, output, failed=False, parent=None, attempt=1):
                rid = str(uuid5(NAMESPACE_URL, PREFIX+issue+'-run-'+suffix))
                task = dict(id=rid, issue_id=issue, issue_identifier=existing[issue]['identifier'],
                    issue_title=existing[issue]['title'], agent_id='workflow-'+role, runtime_id='',
                    status='failed' if failed else 'completed', priority=0, created_at=stamp(minute),
                    dispatched_at=stamp(minute+0.1), started_at=stamp(minute+0.2), completed_at=stamp(minute+4),
                    result=None if failed else {'summary': output}, error='Provider rate limit: retry after 60 seconds' if failed else None,
                    trigger_summary=summary, attempt=attempt, kind='issue',
                    attribution={'initiator': {'id':owner['id'], 'name':owner.get('name') or 'Workspace owner', 'email':owner['email']}, 'source':'direct_assignment', 'precise':True})
                if parent:
                    task['parent_task_id'] = parent
                    task['attribution']['retry_of_task_id' if attempt > 1 else 'delegated_from_task_id'] = parent
                if failed: task['failure_reason'] = 'rate_limit'
                put('task_runs', task)
                events = [
                    ('text', {'content': 'I have picked up this task. '+summary}),
                    ('tool_use', {'tool':'Read', 'call_id':rid+'-read', 'input':{'file_path':issue+'/brief.md'}}),
                    ('tool_result', {'tool':'Read', 'call_id':rid+'-read', 'output':'Scope, accepted input, role ownership and acceptance gates loaded.', 'output_truncated':False}),
                    ('text', {'content':'I will check the accepted input, preserve prior artifacts and report any blocker before handing off.'}),
                    ('tool_use', {'tool':'Bash', 'call_id':rid+'-check', 'input':{'command':'workpal delivery inspect '+existing[issue]['identifier']}}),
                    ('tool_result', {'tool':'Bash', 'call_id':rid+'-check', 'output':'Owner resolved. Parent: TAP-283. Accepted input and downstream handoff references resolved.', 'output_truncated':False}),
                ]
                if failed:
                    events.append(('error', {'content':'Provider returned 429 rate_limit_exceeded. No deliverable was published. Preserve this attempt and start a separate retry after the cooldown.'}))
                else:
                    events.extend([
                        ('tool_use', {'tool':'Write', 'call_id':rid+'-write', 'input':{'file_path':issue+'/report.md','content':output}}),
                        ('tool_result', {'tool':'Write', 'call_id':rid+'-write', 'output':'Saved report; attached to the issue for review.', 'output_truncated':False}),
                        ('text', {'content':output+'\n\nReady for the next review gate. The ticket owner decides the final status.'}),
                    ])
                for seq, (typ, payload) in enumerate(events, 1):
                    put('task_messages', dict(id=rid+'-m'+str(seq),task_id=rid,issue_id=issue,seq=seq,type=typ,created_at=stamp(minute+seq*0.3),**payload))
                activity(issue,'run-'+suffix,minute+4,role,'task_failed' if failed else 'task_completed',{'task_id':rid})
                return rid
            links = '\n'.join(f"- [{i+1:02d} {s['name']} — {existing['lifecycle-'+s['key']]['identifier']}](#/review/issues/lifecycle-{s['key']})" for i,s in enumerate(STAGES))
            for i,s in enumerate(STAGES):
                issue='lifecycle-'+s['key']; minute=i*60
                for role in (s['role'],s['peer']):
                    if not get_record(session,wid,'agents','workflow-'+role): raise RuntimeError('Missing role '+role)
                activity(issue,'created',minute,None,'created',{})
                activity(issue,'assigned',minute+1,None,'assignee_changed',{'to_type':'agent','to_id':'workflow-'+s['role']})
                comment(issue,'brief',minute+2,None,'## Accepted input\n'+s['input']+'\n\n## Requested outcome\n'+s['goal'])
                activity(issue,'started',minute+3,s['role'],'status_changed',{'from':'todo','to':'in_progress'})
                activity(issue,'delegation',minute+4,s['role'],'squad_leader_evaluated',{'outcome':'action','reason':'Request a focused review from '+get_record(session,wid,'agents','workflow-'+s['peer'])['name']+'.'})
                parent=None
                if s['key']=='build':
                    parent=run(issue,'attempt-1',minute+5,s['role'],'Implement the accepted role and squad mapping.','',failed=True)
                    comment(issue,'retry-decision',minute+10,'planner','The first run hit a provider rate limit before publishing an artifact. Keep that attempt for diagnosis. Retry from the same accepted design after the cooldown; do not duplicate registration records.')
                primary=run(issue,'attempt-2' if parent else 'delivery',minute+12,s['role'],s['goal'],s['work'],parent=parent,attempt=2 if parent else 1)
                def artifact(version, at, body, role, source_task):
                    aid=PREFIX+s['key']+'-artifact-v'+str(version)
                    cid=PREFIX+issue+'-artifact-v'+str(version)
                    url='/delivery/'+s['key']+'/'+str(version)+'/'+s['artifact']+'.md'
                    content=f"# {s['name']} — {s['artifact'].replace('-', ' ').title()}\n\nRevision: {version}\nTicket: {existing[issue]['identifier']}\nOwner: {get_record(session,wid,'agents','workflow-'+s['role'])['name']}\n\n"+body+'\n'
                    files[url.lstrip('/')]=content
                    row=dict(id=aid,issue_id=issue,comment_id=cid,chat_session_id=None,chat_message_id=None,
                        uploader_type='agent',uploader_id='workflow-'+role,filename=s['artifact']+'.md',url=url,download_url=url,markdown_url=url,
                        content_type='text/markdown',size_bytes=len(content.encode()),created_at=stamp(at),
                        comment_author_type='agent',comment_author_id='workflow-'+role,comment_created_at=stamp(at))
                    row=put('attachments',row)
                    put('attachment_contents', {'id':aid, 'text':content})
                    comment(issue,'artifact-v'+str(version),at,role,f"## {s['name']} deliverable · v{version}\n\n"+body+f"\n\n[Open {s['artifact']}.md · v{version}]({url})",source_task,[row])
                artifact(1,minute+17,s['work']+'\n\n## Review requested\n'+s['goal'],s['role'],primary)
                peer=run(issue,'review',minute+20,s['peer'],'Review the first revision against the stage acceptance gate.',s['review'])
                comment(issue,'review',minute+25,s['peer'],'## Review findings\n\n'+s['review'],peer)
                revised=run(issue,'revision',minute+27,s['role'],'Address the review and prepare revision 2.',s['output'])
                artifact(2,minute+32,s['artifact_body'],s['role'],revised)
                activity(issue,'ready',minute+34,s['role'],'status_changed',{'from':'in_progress','to':'in_review'})
                approval='Approved for release. QA evidence, security review and rollback ownership are complete.' if s['key']=='deploy' else ('Initial review accepted. Keep this ticket open for the next source update.' if s['key']=='maintain' else 'Approved. Revision 2 addresses the review and satisfies this stage’s acceptance gate.')
                comment(issue,'approval',minute+37,None,'## Owner decision\n\n'+approval+'\n\n'+s['output'])
                final_status='in_progress' if i==5 else 'done'
                activity(issue,'accepted',minute+38,None,'status_changed',{'from':'in_review','to':final_status})
                nxt=STAGES[(i+1)%6]; nxt_id='lifecycle-'+nxt['key']
                comment(issue,'handoff',minute+40,s['role'],f"## Handoff → {nxt['name']}\n\n**Input:** {s['artifact'].replace('-', ' ')} v2.\n\n**Outcome:** {s['output']}\n\n**Receiving owner:** {get_record(session,wid,'agents','workflow-'+nxt['role'])['name']}.\n\n[Continue to {nxt['name']} · {existing[nxt_id]['identifier']}](#/review/issues/{nxt_id}) · [Delivery overview](#/review/issues/lifecycle-delivery)")
                prev='lifecycle-delivery' if i==0 else 'lifecycle-'+STAGES[i-1]['key']
                row={**existing[issue], 'status':final_status, 'created_at':stamp(minute),'updated_at':stamp(minute+40),
                    'description':f"## Outcome\n{s['goal']}\n\n## Accepted input\n{s['input']}\n\n## Acceptance gate\n{s['output']}\n\n## Evidence\n- [Deliverable v1](/delivery/{s['key']}/1/{s['artifact']}.md)\n- [Reviewed deliverable v2](/delivery/{s['key']}/2/{s['artifact']}.md)\n- Activity contains review findings and the owner decision; Runs contains the execution transcripts.\n\n## Handoff\n[Previous stage](#/review/issues/{prev}) · [Next: {nxt['name']}](#/review/issues/{nxt_id}) · [Parent delivery](#/review/issues/lifecycle-delivery)"}
                put('issues',row)
                # Retain original local evidence in an internal archive, not in the authored story.
                from workpal_backend.workspace_content.repository import delete_record
                for old in list_records(session,wid,'comments'):
                    if old.get('issue_id')==issue and old['id'].startswith('lifecycle-') and not old['id'].startswith(PREFIX):
                        put_record(session,wid,'archived_evidence_comments',old)
                        delete_record(session,wid,'comments',old['id'])
            parent=existing['lifecycle-delivery']
            put('issues',{**parent,'created_at':stamp(0),'updated_at':stamp(340),'completed_sub_issue_count':5,
                'description':'## Workflow team delivery\nOne delivery route from accepted scope to ongoing maintenance.\n\n'+links+'\n\n## Review route\n1. Plan: scope and owner acceptance.\n2. Design: stable identity and architecture review.\n3. Build: failed first attempt, separate retry and code review.\n4. Test: finding Q-01, fix and re-verification.\n5. Deploy: security review, human approval and rollback.\n6. Maintain: initial review accepted; next source update remains open.\n\nOpen **Activity** for decisions and **Runs** for transcripts. Deliverables retain both revisions.'})
            comment('lifecycle-delivery','summary',341,'planner','## Delivery checkpoint\n\nPlan through Deploy are accepted. Maintain owns the next source update.\n\n'+links+'\n\nThe Build rate-limit failure and its successful retry remain separate runs; review feedback and owner decisions are retained with each stage.')
            project=get_record(session,wid,'projects','workflow-delivery')
            put('projects',{**project,'description':'Source-backed roles and squads, delivered through six accountable stages.\n\n'+links,'issue_count':7,'done_count':5})
        for relative,content in files.items():
            path=ROOT/'apps/web/public'/relative
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(content)
        print(json.dumps({'issues':7,'stages':6,'runs':19,'deliverable_revisions':len(files),'backup':backup}))
    finally:
        db.close()


if __name__=='__main__':
    seed_story()
