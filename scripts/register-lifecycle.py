"""Build a traceable local delivery record from observed repository evidence.
No model runs, deployment approvals or backdated events are synthesized.
"""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import re
import sqlite3
import urllib.request
from sqlalchemy import select, update
from workpal_backend.config import Settings
from workpal_backend.infrastructure.database import Database
from workpal_backend.auth.models import users
from workpal_backend.workspaces.models import workspaces, members
from workpal_backend.workspace_content.repository import get_record, put_record, list_records

ROOT = Path(__file__).resolve().parents[1]
PROJECT = 'workflow-delivery'
PARENT = 'lifecycle-delivery'


def register():
    settings = Settings()
    if not settings.dev_auth:
        raise RuntimeError('Local development authentication is required')
    data = ROOT/'apps/web/app/capabilities/data'
    stages = json.loads((data/'stages.json').read_text())
    roles = json.loads((data/'role-profiles.json').read_text())
    catalog = json.loads((data/'catalog.json').read_text())
    archived_log = ROOT/'server/data/lifecycle-evidence/source-team-check.log'
    check = (archived_log if archived_log.exists() else Path('/tmp/workpal-sourced-team-check.log')).read_text()
    if not re.search(r'\d+ passed', check) or 'built in' not in check or 'FAILED ' in check:
        raise RuntimeError('Successful source-team check log required')
    checks = '\n'.join(line for line in check.splitlines() if re.search(r'\d+ passed|built in',line))
    with urllib.request.urlopen('http://127.0.0.1:4175/healthz') as response:
        health = json.load(response)
    if health.get('status') != 'ok':
        raise RuntimeError('Local service is not healthy')
    stamp = datetime.now(timezone.utc).isoformat()
    db = Database(settings)
    try:
        backup = Path(db.engine.url.database + '.before-lifecycle-' + datetime.now().strftime('%Y%m%d%H%M%S%f'))
        with sqlite3.connect(db.engine.url.database) as source, sqlite3.connect(backup) as target:
            source.backup(target)
        with db.transaction() as session:
            owner = session.execute(select(users).where(users.c.email=='workpal@fwd.com')).mappings().one()
            ws = session.execute(select(workspaces).where(workspaces.c.slug=='review')).mappings().one()
            membership = session.execute(select(members).where(members.c.workspace_id==ws['id'],members.c.user_id==owner['id'])).mappings().one()
            assert membership['role'] in ('owner','admin')
            wid=ws['id']; base=dict(workspace_id=wid,created_at=stamp,updated_at=stamp,creator_id=owner['id'],creator_type='member',priority='medium',labels=[],metadata={},properties={},visibility='workspace',position=0,icon=None,lead_id=None,lead_type=None,start_date=None,due_date=None)
            def insert(kind,body):
                if get_record(session,wid,kind,body['id']) is None:put_record(session,wid,kind,body)
            # Bind catalog descriptions, not executable installations. Existing bindings survive.
            skills={s['id']:s for s in catalog['skills']}
            for role in roles:
                agent=get_record(session,wid,'agents','workflow-'+role['id'])
                if not agent:raise RuntimeError('Register workflow teams first')
                assigned=list(agent.get('skills',[]));seen={s['id'] for s in assigned}
                method_ids=list(role['skills'])
                if role['id']=='experimenter':
                    sid='workflow-autoresearch-protocol'
                    skills[sid]={'name':'Autoresearch protocol','description':'Prepare bounded experiments with a fixed evaluation, baseline and results ledger. Source instructions only; training is not executed here.','url':role['sourceUrl']}
                    method_ids.append(sid)
                for sid in method_ids:
                    source=skills[sid]
                    skill=dict(base,id=sid,name=source['name'],description=source['description'],source=source['url'],created_by=owner['id'],config={},enabled=True,metadata={'source_url':source['url'],'registration':'description_only'})
                    insert('skills',skill)
                    if sid not in seen:assigned.append(get_record(session,wid,'skills',sid));seen.add(sid)
                agent['skills']=assigned
                put_record(session,wid,'agents',agent)
            snapshots={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [data/'role-profiles.json',data/'squads.json',ROOT/'apps/web/app/capabilities/overview.tsx',ROOT/'scripts/register-workflow-team.py']}
            evidence={'recorded_at':stamp,'kind':'observed_local_setup','source_check_log_sha256':hashlib.sha256(check.encode()).hexdigest(),'source_check_summary':checks,'health':health,'file_sha256':snapshots,'execution':'No model execution or production deployment'}
            evidence_path=ROOT/'server/data/lifecycle-evidence.json'
            # Write the initial observation once, matching immutable initial ticket notes.
            # Publish the evidence only after the database commit succeeds.
            links='\n'.join(f"- [{i+1:02d} {s['name']}](#/review/issues/lifecycle-{s['id']})" for i,s in enumerate(stages))
            provenance='This is a retrospective record of local work performed in this repository. Role assignments describe responsibility; they are not evidence that an autonomous agent executed the task. Notes are recorded now by local setup tooling under the default account, not backdated conversations.'
            insert('projects',dict(base,id=PROJECT,title='Workflow team delivery',name='Workflow team delivery',status='in_progress',description=provenance+'\n\n## Delivery sequence\n'+links,issue_count=7,done_count=5))
            counter=max(ws['issue_counter'],max((r.get('number',0) or 0 for r in list_records(session,wid,'issues')),default=0))
            def issue(id,title,description,status,assignee,parent=None):
                nonlocal counter
                if get_record(session,wid,'issues',id):return
                counter+=1
                insert('issues',dict(base,id=id,number=counter,identifier=f"{ws['issue_prefix']}-{counter}",title=title,description=description,status=status,assignee_type='agent',assignee_id='workflow-'+assignee,parent_issue_id=parent,project_id=PROJECT,sub_issue_count=6 if parent is None else 0,completed_sub_issue_count=5 if parent is None else 0,metadata={'provenance':'recorded_local_work','recorded_at':stamp}))
            issue(PARENT,'Deliver sourced workflow teams',provenance+'\n\n'+links+'\n\nStages 01–05 record completed local configuration work. Stage 06 remains open for ongoing upkeep. No production release or model execution is claimed.','in_progress','planner')
            bodies=[
              ('intent','done','Scope brief','Replace vague role labels; remove repeated Overview navigation; register sourced roles and squads in the workspace. Preserve existing records. Acceptance: every role has a source, every squad has a resolvable leader, and both catalogs and workspace agree.','User requested these changes in this session. Scope was implemented in the prior delivery; no separate product approval is claimed.'),
              ('design-role','done','Design record','Keep stable role IDs and attach source author plus pinned workflow URL. Use recognizable job titles. Treat cross-workflow squads as Workpal adaptations. Reuse the existing SQLite workspace and preserve historical records.','The catalog contains 15 roles and 5 squads. Sources cover pstack, gstack, Matt Pocock skills and autoresearch. Role profiles disclose adaptation.'),
              ('implementation','done','Change record','Role catalog, squad catalog, source links, Overview cleanup and idempotent SQLite registration were implemented. Registration creates offline agents without executing models.','Changed files and their SHA-256 digests:\n\n'+ '\n'.join(f'- `{p}`: `{sha}`' for p,sha in snapshots.items())),
              ('verifier','done','Verification record','Acceptance checks: role/source integrity, squad references, navigation and no repeated Overview promotions. Verify that registration does not duplicate or overwrite existing records.','Prior delivery verification, before this lifecycle registration:\n\n```text\n'+checks+'\n```\n\nSource log SHA-256: `'+hashlib.sha256(check.encode()).hexdigest()+'`. Browser checks in this session also read 15 registered roles and 5 registered squads. These are local configuration checks, not model benchmarks.'),
              ('pipeline','done','Local release record','The active application serves the changed frontend and registered SQLite records locally. Scope is the local service only. Recovery: stop local writers, preserve the current database, and restore a verified SQLite backup if needed. Do not reset existing records.','Observed at '+stamp+': GET http://127.0.0.1:4175/healthz returned '+json.dumps(health)+'. Local registration created a SQLite backup before writes. No production deployment or production authorization occurred.'),
              ('monitoring','todo','Maintenance handoff','On the next source update, compare pinned revisions, review changed role responsibilities and rerun catalog and workspace checks. Preserve current records and log accepted changes.','No production incident, monitoring result or completed maintenance run is claimed. This is pending follow-up work. Exit criteria: one reviewed source update with fresh validation evidence.')]
            for i,(stage,(assignee,status,artifact,body,observation)) in enumerate(zip(stages,bodies)):
                id='lifecycle-'+stage['id']
                navigation='[Delivery overview](#/review/issues/'+PARENT+')\n\n'+links
                description=f"## {i+1:02d} {stage['name']} — {artifact}\n\n{body}\n\n## Evidence\n\n{observation}\n\n## Handoff\n\n"+('Next: '+stages[i+1]['name'] if i<5 else 'Feed accepted follow-up back into Plan.')+'\n\n'+navigation+'\n\n## Record provenance\n\n'+provenance
                issue(id,f"{i+1:02d} {stage['name']} — Workflow team delivery",description,status,assignee,PARENT)
                note=dict(id=id+'-record',workspace_id=wid,issue_id=id,author_type='member',author_id=owner['id'],content='Recorded by local setup tooling under workpal@fwd.com. This is an evidence note, not an agent-authored execution transcript.\n\n'+observation,type='comment',created_at=stamp,updated_at=stamp,metadata={'provenance':'observed_local_setup' if i<5 else 'pending_follow_up'})
                insert('comments',note)
            session.execute(update(workspaces).where(workspaces.c.id==wid).values(issue_counter=counter))
        if not evidence_path.exists():
            temporary = evidence_path.with_suffix('.json.tmp')
            temporary.write_text(json.dumps(evidence,indent=2)+'\n')
            temporary.replace(evidence_path)
        print(json.dumps({'project':PROJECT,'parent':PARENT,'stages':6,'maintenance':'pending','backup':str(backup)}))
    finally:db.close()


if __name__=='__main__':register()
