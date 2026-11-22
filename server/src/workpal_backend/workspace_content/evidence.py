"""Append-only delivery documents and authenticated, revision-specific decisions."""
from datetime import datetime, timezone
from hashlib import sha256
from uuid import uuid4
from fastapi import HTTPException
from . import repository as repo

FIELDS = {
    'requirements': ('criteria', 'exclusions'),
    'design': (),
    'code': ('diff', 'findings', 'fixes', 'recheck'),
    'test': ('method', 'results', 'failures', 'uncovered'),
    'handoff': ('scope', 'remaining'),
}


def text(body, key):
    value = body.get(key)
    if not isinstance(value, str) or not value.strip():
        raise HTTPException(400, key + ' is required')
    if len(value) > 500_000:
        raise HTTPException(400, key + ' is too large')
    return value.strip()


def inventory(session, wid, iid):
    revisions = [r for r in repo.list_records(session, wid, 'delivery_revisions') if r['issue_id'] == iid]
    reviews = [r for r in repo.list_records(session, wid, 'delivery_reviews') if r['issue_id'] == iid]
    # Submission is not verification, even when every structured field is populated.
    return {'revisions': revisions, 'reviews': reviews,
            'runs': {r['run_id']: repo.get_record(session, wid, 'task_runs', r['run_id']) for r in revisions if r.get('run_id')},
            'inputs': {key: repo.get_record(session, wid, 'delivery_revisions', key) for r in revisions for key in r['input_ids']},
            'status': 'review_required' if revisions else 'evidence_pending', 'requirements': FIELDS}


def publish(session, workspace, principal, issue, body):
    wid, iid = workspace['id'], issue['id']
    now = datetime.now(timezone.utc).isoformat()
    rid, cid = str(uuid4()), str(uuid4())
    def linked(kind, key, same_issue=True):
        value = body.get(key)
        row = repo.get_record(session, wid, kind, value) if isinstance(value, str) else None
        if not row or (same_issue and row.get('issue_id') != iid):
            raise HTTPException(400, 'Invalid ' + key)
        return row
    common = {'id': rid, 'workspace_id': wid, 'issue_id': iid, 'created_at': now, 'activity_id': cid}
    attachment = None
    if 'review_of' in body:
        target = linked('delivery_revisions', 'review_of')
        decision = body.get('decision')
        if decision not in ('accepted', 'changes_requested', 'reviewed'):
            raise HTTPException(400, 'Invalid decision')
        row = {**common, 'review_of': target['id'], 'decision': decision,
               'scope': text(body, 'scope'), 'remaining': text(body, 'remaining'), 'reviewer_id': principal.user_id}
        repo.put_record(session, wid, 'delivery_reviews', row)
        content = f"## Delivery review · {decision}\n\n{target['title']} · v{target['version']}\nRevision: {target['id']}\nSHA-256: {target['sha256']}\n\nScope: {row['scope']}\n\nRemaining: {row['remaining']}"
    else:
        kind = body.get('kind')
        if not isinstance(kind, str) or kind not in FIELDS:
            raise HTTPException(400, 'Invalid deliverable kind')
        title, content = text(body, 'title'), text(body, 'content')
        sections = {key: text(body, key) for key in FIELDS[kind]}
        inputs = body.get('input_ids', [])
        if not isinstance(inputs, list) or any(not isinstance(v, str) or not repo.get_record(session, wid, 'delivery_revisions', v) for v in inputs):
            raise HTTPException(400, 'Invalid input revisions')
        if kind == 'handoff' and not inputs:
            raise HTTPException(400, 'Handoff requires exact input revisions')
        previous = linked('delivery_revisions', 'previous_id') if body.get('previous_id') else None
        if previous and (previous['kind'] != kind or previous['title'] != title):
            raise HTTPException(400, 'Revision must retain document title and kind')
        family = previous['document_id'] if previous else rid
        revisions = inventory(session, wid, iid)['revisions']
        if previous and any(r.get('previous_id') == previous['id'] for r in revisions):
            raise HTTPException(409, 'A newer revision exists')
        run = linked('task_runs', 'run_id') if body.get('run_id') else None
        if run and (run.get('_fixture') or run.get('fixture_source')):
            raise HTTPException(400, 'Run has no verified execution evidence')
        full = content + ''.join(f'\n\n## {key.title()}\n{value}' for key, value in sections.items())
        row = {**common, 'document_id': family, 'previous_id': previous['id'] if previous else None,
               'version': previous['version'] + 1 if previous else 1, 'kind': kind, 'title': title,
               'content': full, 'sections': sections, 'input_ids': inputs, 'run_id': run['id'] if run else None,
               'author_id': principal.user_id, 'sha256': sha256(full.encode()).hexdigest(), 'attachment_id': rid}
        repo.put_record(session, wid, 'delivery_revisions', row)
        url = '/api/attachments/' + rid + '/content'
        attachment = {'id': rid, 'workspace_id': wid, 'issue_id': iid, 'comment_id': cid,
                      'filename': title.replace('/', '-')[:120] + '.md', 'content_type': 'text/markdown',
                      'size_bytes': len(full.encode()), 'created_at': now, 'url': url, 'download_url': url,
                      'uploader_type': 'member', 'uploader_id': principal.user_id, 'authenticated_download': True}
        repo.put_record(session, wid, 'attachments', attachment)
        repo.put_record(session, wid, 'attachment_contents', {'id': rid, 'text': full})
        content = f"## Deliverable submitted · {title} · v{row['version']}\n\nReview required.\nRevision: {rid}\nSHA-256: {row['sha256']}"
        if inputs:
            content += '\n\nInput revisions: ' + ', '.join(inputs)
    comment = {'id': cid, 'workspace_id': wid, 'issue_id': iid, 'type': 'comment',
               'author_type': 'member', 'author_id': principal.user_id, 'content': content,
               'created_at': now, 'updated_at': now, 'revision': 1, 'attachments': [attachment] if attachment else []}
    if row.get('run_id'):
        comment['source_task_id'] = row['run_id']
    repo.put_record(session, wid, 'comments', comment)
    return row
