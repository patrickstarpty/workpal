"""Publish actual local verification evidence, never backdate or impersonate old Runs.
Default rolls back. --apply backs up SQLite and commits the reviewed reports.
"""
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import select
from workpal_backend.config import Settings
from workpal_backend.infrastructure.database import Database
from workpal_backend.auth.dependencies import Principal
from workpal_backend.auth.models import users
from workpal_backend.workspaces.models import workspaces
from workpal_backend.workspace_content import repository as repo
from workpal_backend.workspace_content.evidence import publish

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/handoffs/smart-deliverables'
KEY='smart-local-verification-2026-11-22-v1'


def publish_reports(session):
 workspace=dict(session.execute(select(workspaces).where(workspaces.c.slug=='workpal-team')).mappings().one())
 owner=session.execute(select(users).where(users.c.email=='workpal@fwd.com')).mappings().one()
 wid=workspace['id']; principal=Principal(owner['id'])
 manifest=json.loads((BASE/'source-snapshot/manifest.json').read_text())
 reports=[]
 for number in (4,7,10,15):
  iid=f'workflow-work-{number:02d}'
  issue=repo.get_record(session,wid,'issues',iid)
  if not issue: raise RuntimeError('Missing '+iid)
  key=KEY+'-'+iid
  existing=repo.get_record(session,wid,'evidence_imports',key)
  if existing:
   reports.append(existing);continue
  upload=number in (7,10)
  logfile='upload-verification.txt' if upload else 'title-draft-verification.txt'
  log=(BASE/logfile).read_text()
  expected='15 passed' if upload else '22 passed'
  if expected not in log:raise RuntimeError('Unexpected verification output')
  selected=[f for f in manifest['files'] if (f['path'].startswith('server/'))==upload]
  snapshots=[]
  for file in selected:
   data=(BASE/'source-snapshot'/file['path']).read_bytes()
   if hashlib.sha256(data).hexdigest()!=file['sha256']:raise RuntimeError('Changed snapshot')
   snapshots.append(f"## {file['path']}\nSHA-256: {file['sha256']}\n\n```text\n{data.decode()}\n```")
  comments=[r for r in repo.list_records(session,wid,'comments') if r.get('issue_id')==iid and r.get('_fixture')]
  references='\n'.join(f"- Activity {r['id']}; historical Run {r.get('source_task_id') or 'none'}" for r in comments)
  method=('server/.venv/bin/python -m pytest server/tests/test_upload_recovery.py server/tests/test_upload_worker_recovery.py server/tests/test_attachment_uploads.py -v' if upload else 'pnpm --filter @workpal/views test editor/title-editor.test.tsx editor/title-editor.shortcut.test.tsx chat/components/chat-input-draft-isolation.test.tsx')
  body={'kind':'test','title':issue['identifier']+' local verification report',
   'content':f"# {issue['identifier']} verification report · revision 1\n\nPrepared by Codex in the current evidence audit, on behalf of the requesting user. No owner acceptance is recorded. These commands were actually executed locally; this is not an output of a historical agent Run.\n\nCheckout HEAD: {manifest['head']}. Exact inspected source is attached below; the checkout also contains uncommitted work.\n\n"+(BASE/'verification-findings.md').read_text().split('## Publication status')[0]+'\n\n## Historical records being checked\n'+references,
   'method':method,'results':expected+'\n\nRaw process output:\n```text\n'+log+'\n```',
   'failures':'No failures in the executed subset. Evidence gap U-01: no verified browser partial-transfer resume.' if upload else 'No failures in the executed subset. Mocked editor tests do not establish browser accessibility acceptance.',
   'uncovered':'Browser reconnect, partial-transfer offset resume, authorization expiry during reconnect, cancellation during reconnect, refresh recovery, external storage and release approval.' if upload else 'Real Tiptap accessible names, screen reader announcements, browser save/cancel focus restoration, narrow title layout, complete workspace-switch/refresh/sign-out/revoked-membership scenarios.'}
  revision=publish(session,workspace,principal,issue,body)
  attachment_id=revision['id']+'-sources'
  content='# Inspected source snapshot\n\n'+ '\n\n'.join(snapshots)
  attachment={'id':attachment_id,'workspace_id':wid,'issue_id':iid,'comment_id':revision['activity_id'],'filename':issue['identifier']+'-verification-sources.md','content_type':'text/markdown','size_bytes':len(content.encode()),'created_at':revision['created_at'],'url':'/api/attachments/'+attachment_id+'/content','download_url':'/api/attachments/'+attachment_id+'/download','authenticated_download':True,'uploader_type':'member','uploader_id':owner['id']}
  repo.put_record(session,wid,'attachments',attachment)
  repo.put_record(session,wid,'attachment_contents',{'id':attachment_id,'text':content})
  comment=repo.get_record(session,wid,'comments',revision['activity_id'])
  comment['attachments'].append(attachment)
  comment['content']+='\n\nPrepared by Codex from actual local verification. Historical Run claims are reviewed, not adopted. See report for actual results, source versions and uncovered acceptance criteria.'
  repo.put_record(session,wid,'comments',comment)
  record={'id':key,'issue_id':iid,'revision_id':revision['id'],'activity_id':revision['activity_id'],'sources_attachment_id':attachment_id,'source_sha256':hashlib.sha256(log.encode()).hexdigest()}
  repo.put_record(session,wid,'evidence_imports',record);reports.append(record)
 for number in (1,2,3,8,12,13,14,16,5,6,11,17,18,19,20,21,9):
  iid=f'workflow-work-{number:02d}';key='smart-specification-2026-11-22-v1-'+iid
  existing=repo.get_record(session,wid,'evidence_imports',key)
  if existing:
   reports.append(existing);continue
  issue=repo.get_record(session,wid,'issues',iid)
  if not issue:raise RuntimeError('Missing '+iid)
  content=(BASE/'specifications'/f'SMART-{number}.md').read_text()
  body={'kind':'requirements' if number in (1,3,13) else 'design','title':issue['identifier']+' '+('recovery requirements' if number==13 else 'interaction specification'),'content':content}
  if number in (1,3,13):
   body.update(criteria='The explicit acceptance/verification cases in this document require actual evidence before acceptance.',exclusions='No production execution, external storage certification, implicit owner approval or unsupported resume guarantee.')
  if number==9:
   body.update(kind='code',diff=(BASE/'relationship-working-tree.diff').read_text() or 'No working-tree difference from the recorded baseline.',findings='R9-01 workspace boundary supported by targeted test; R9-02 full navigation unverified; R9-03 diff is not ticket-specific.',fixes='No product fixes made in this audit. R9-02 and R9-03 remain open.',recheck=(BASE/'relationship-verification.txt').read_text())
  if number in (5,11,17):
   body.update(kind='handoff',input_ids=[r['revision_id'] for r in reports if r['issue_id'] in ('workflow-work-07','workflow-work-08','workflow-work-10','workflow-work-13','workflow-work-16')],scope='Review the exact referenced package; no release authorized.',remaining='Implementation diff, browser regression, external storage verification and explicit owner approval remain missing.')
  revision=publish(session,workspace,principal,issue,body)
  comment=repo.get_record(session,wid,'comments',revision['activity_id'])
  comment['content']+='\n\nPrepared by Codex in the current evidence repair. This full specification is submitted for review; historical approval is not asserted. It is not an output of an earlier agent Run.'
  repo.put_record(session,wid,'comments',comment)
  record={'id':key,'issue_id':iid,'revision_id':revision['id'],'activity_id':revision['activity_id']}
  repo.put_record(session,wid,'evidence_imports',record);reports.append(record)
 for number in (7,15):
  iid=f'workflow-work-{number:02d}';key='smart-development-audit-2026-11-22-v1-'+iid
  existing=repo.get_record(session,wid,'evidence_imports',key)
  if existing:
   reports.append(existing);continue
  issue=repo.get_record(session,wid,'issues',iid)
  upload=number==7
  diff=(BASE/('upload-working-tree.diff' if upload else 'title-working-tree.diff')).read_text()
  findings=('D7-01: historical progress claims one upload identity across retries; no task-specific commit, offset-resume protocol or executed browser trace establishes that behavior. D7-02: the recorded rate-limit failure and retry belong to authored history, not measured execution. D7-03: local recovery tests exercise expired-intent cleanup and fencing, not browser partial-transfer continuation.' if upload else 'D15-01: no task-specific semantic title change was identified. Git history for title-editor.tsx shows frontend import and branding changes, not the claimed accessible-name correction. D15-02: tests mock EditorContent, so they do not prove real accessible names or focus restoration. D15-03: the historical owner acceptance has no authenticated exact-version decision.')
  report=next(r for r in reports if r['issue_id']==iid)
  content=f"# {issue['identifier']} development claim review\n\nRevision 1. Prepared by Codex during this audit, not by the historical Run. No acceptance is recorded.\n\n## Exact baseline and comparison\nBase HEAD: b93ed96078c90605230b81fdbf240f65f1c93437. Comparison: git diff HEAD -- " + ('server/src/workpal_backend/files' if upload else 'packages/views/editor/title-editor.tsx') + ". This is a current source comparison, not an attributed historical task patch.\n\n## Review findings\n"+findings+f"\n\n## Verified input\nLocal test report revision {report['revision_id']}; producing Activity {report['activity_id']}. That report contains raw results and exact inspected source snapshots.\n\n## Correction and recheck ledger\nNo implementation correction was performed by this audit. The findings remain open. Rechecking the existing test subset confirms only the narrow behaviors described in the report. No independently reviewed fix or browser acceptance result was found.\n\n## Required handoff\nThe delivery owner must identify the original scoped commit/patch, or implement the missing behavior under an explicit scope. Then provide review findings, the actual corrective diff and a fresh recheck of the affected acceptance criteria. Preserve the historical record but do not treat its completion/acceptance wording as proof."
  body={'kind':'code','title':issue['identifier']+' development claim review','content':content,'input_ids':[report['revision_id']], 'diff':diff or 'The exact git diff command returned an empty diff. No uncommitted changes exist in this inspected path; this is not evidence of a historical implementation fix.', 'findings':findings,'fixes':'No product fix performed. All listed evidence gaps remain open.','recheck':'See exact referenced local test report. No verified historical code review, correction or owner acceptance was recovered.'}
  revision=publish(session,workspace,principal,issue,body)
  record={'id':key,'issue_id':iid,'revision_id':revision['id'],'activity_id':revision['activity_id']}
  repo.put_record(session,wid,'evidence_imports',record);reports.append(record)
 return reports


def main():
 settings=Settings()
 if not settings.dev_auth:raise RuntimeError('Requires local development backend')
 db=Database(settings);apply='--apply' in sys.argv
 try:
  if apply:
   backup=str(db.engine.url.database)+'.before-smart-evidence-'+datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')
   with sqlite3.connect(db.engine.url.database) as source,sqlite3.connect(backup) as target:source.backup(target)
  with db.transaction() as session:
   result=publish_reports(session)
   if not apply:session.rollback()
  (BASE/('published-verification.json' if apply else 'publication-preview.json')).write_text(json.dumps(result,indent=2)+'\n')
  print(json.dumps({'applied':apply,'reports':len(result),'backup':backup if apply else None}))
 finally:db.close()

if __name__=='__main__':main()
