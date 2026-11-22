"""Production-mounted local-interest boundaries; source fixtures are not Go execution."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from test_onboarding_json_edges import authenticated
from workpal_backend.app import create_app

PATH = '/api/me/onboarding/cloud-waitlist'
SOURCE = json.loads((Path(__file__).parents[1] / 'contracts/batches/onboarding-completion.json').read_text())
# JSON null leaves Go's zero-valued request struct; email validation follows.
CASES = [f for f in SOURCE['fixtures'] if f['route'] == 'cloud-waitlist'
         and 'body' in f]


@pytest.fixture(autouse=True)
def populated_related_rows(authenticated):
    client, headers = authenticated
    created = client.post('/api/workspaces', json={'name': 'Retained', 'slug': 'retained'}, headers=headers)
    assert created.status_code == 201
    workspace_id = created.json()['id']
    changed = client.patch('/api/workspaces/' + workspace_id, json={'name': 'Still retained'}, headers=headers)
    assert changed.status_code == 200
    state = snapshot(client)
    assert state['workspaces'] and state['members'] and state['outbox']


def snapshot(client):
    with client.app.state.database.transaction() as session:
        # Actual tables, unconditionally: also catches schema/fixture assumptions.
        return {name: [tuple(r) for r in session.execute(text(f'SELECT * FROM "{name}" ORDER BY rowid'))]
                for name in ('users', 'workspaces', 'members', 'outbox')}


@pytest.mark.parametrize('case', CASES)
def test_source_waitlist_cases(authenticated, case):
    client, headers = authenticated
    before = snapshot(client)
    raw = case['body'] if isinstance(case['body'], str) else json.dumps(case['body'])
    response = client.post(PATH, content=raw, headers=headers)
    assert response.status_code == case['status'], response.text
    after = snapshot(client)
    if case['status'] != 200:
        assert response.json() == case['response']
        assert after == before
    else:
        assert response.json()['onboarded_at'] is None
        assert 'cloud_waitlist_email' not in response.json()
        for table in before.keys() - {'users'}:
            assert after[table] == before[table]


@pytest.mark.parametrize('body,status,error', [
    ({'email':'a@example.com','reason':'é'*250},200,None),
    ({'email':'a@example.com','reason':'é'*251},400,'reason is too long'),
    ({'email':'a'*64+'@'+'b'*63+'.'+'c'*63+'.'+'d'*61},200,None),
    ({'email':'a'*64+'@'+'b'*63+'.'+'c'*63+'.'+'d'*62},400,'email is too long'),
])
def test_byte_limits(authenticated, body, status, error):
    client, headers = authenticated
    before = snapshot(client)
    response = client.post(PATH, json=body, headers=headers)
    assert response.status_code == status, response.text
    if error:
        assert response.json() == {'error':error}
        assert snapshot(client) == before


def test_auth_boundaries(authenticated):
    client, headers = authenticated
    before = snapshot(client)
    for csrf in ({}, {'x-csrf-token':'wrong'}):
        assert client.post(PATH,json={'email':'a@example.com'},headers=csrf).status_code == 403
        assert snapshot(client) == before
    csrf = client.cookies.get('workpal_csrf')
    assert client.post(PATH,json={'email':'a@example.com'},headers={'x-csrf-token':csrf}).status_code == 200
    client.post('/auth/logout')
    before = snapshot(client)
    assert client.post(PATH,json={'email':'a@example.com'},headers={k:v+'tampered' for k,v in headers.items()}).status_code == 401
    client.cookies.clear()
    assert client.post(PATH,json={'email':'a@example.com'}).status_code == 401
    assert snapshot(client) == before


def test_bounded_stream_rejection(authenticated):
    client, headers = authenticated
    before = snapshot(client)
    response = client.post(PATH,content=iter([b' '*8192,b' '*8192,b' ']),headers=headers)
    assert response.status_code == 413
    assert response.json() == {'error':'request body too large'}
    assert snapshot(client) == before


def test_repeat_reopen_preserves_exact_questionnaire(authenticated, settings):
    client, headers = authenticated
    raw = b'{"n":0.12345678901234567890123456789,"cloud_waitlist_email":"keep"}'
    with client.app.state.database.transaction() as session:
        session.execute(text('UPDATE users SET onboarding_questionnaire=:q, onboarded_at=:at'),
                        {'q':raw,'at':'2026-11-20T00:00:00Z'})
    before = snapshot(client)
    for email, reason in [('first@example.com','interest'),('second@example.com','  ')]:
        response = client.post(PATH,json={'email':email,'reason':reason},headers=headers)
        assert response.status_code == 200
        assert response.json()['onboarded_at'] == '2026-11-20T00:00:00Z'
    with TestClient(create_app(settings)) as reopened:
        with reopened.app.state.database.transaction() as session:
            row = session.execute(text('SELECT * FROM users')).mappings().one()
            assert row['cloud_waitlist_email'] == 'second@example.com'
            assert row['cloud_waitlist_reason'] is None
            assert row['onboarding_questionnaire'] == raw
            assert row['onboarded_at'] == '2026-11-20T00:00:00Z'
        after = snapshot(reopened)
        for table in before.keys() - {'users'}:
            assert after[table] == before[table]
