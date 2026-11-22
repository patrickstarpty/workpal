"""Verify business records and document downloads using only a temporary SQLite copy."""
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
from fastapi.testclient import TestClient
from workpal_backend.app import create_app
from workpal_backend.config import Settings
from workpal_backend.auth.tokens import issue_session

source = Settings().database_url.removeprefix('sqlite:///')
with sqlite3.connect(source) as original, tempfile.TemporaryDirectory() as folder:
    target = Path(folder) / 'workpal.sqlite'
    with sqlite3.connect(target) as destination:
        original.backup(destination)
    accounts = original.execute("""
        SELECT w.id,w.slug,u.id,u.email,u.name FROM workspaces w
        JOIN members m ON w.id=m.workspace_id JOIN users u ON u.id=m.user_id
        WHERE m.role='owner'
    """).fetchall()
    settings = Settings(database_url='sqlite:///' + str(target),
                        auth_secret='isolated-portability-test-secret-32')
    records_seen, documents_seen = set(), set()
    with TestClient(create_app(settings)) as client:
        for wid, slug, uid, email, name in accounts:
            token = issue_session(uid, email, name, settings.auth_secret, 3600)
            headers = {'Authorization': 'Bearer ' + token, 'X-Workspace-Slug': slug}
            rows = original.execute('SELECT kind,body FROM workspace_records WHERE workspace_id=?', (wid,)).fetchall()
            for kind, body in rows:
                row = json.loads(body)
                if kind in ('issues', 'projects', 'agents', 'skills', 'squads', 'autopilots', 'labels'):
                    response = client.get('/api/' + kind + '/' + row['id'], headers=headers)
                    assert response.status_code == 200, (kind, row['id'], response.status_code)
                    assert response.json() == row, (kind, row['id'])
                    records_seen.add((wid, kind, row['id']))
                if kind == 'attachments':
                    response = client.get('/api/attachments/' + row['id'] + '/download', headers=headers)
                    assert response.status_code == 200, (row['filename'], response.status_code)
                    assert hashlib.sha256(response.content).hexdigest() == row['sha256'], row['filename']
                    timeline = client.get('/api/issues/' + row['issue_id'] + '/timeline', headers=headers).json()
                    assert any(any(a['id'] == row['id'] for a in c.get('attachments', []))
                               for c in timeline), row['filename']
                    documents_seen.add((wid, row['id']))
    print('SQLite-only copy:', len(records_seen), 'business records and', len(documents_seen), 'documents verified through HTTP.')
