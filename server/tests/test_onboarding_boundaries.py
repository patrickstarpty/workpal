"""Mounted onboarding failures and observable ASGI receive boundaries."""
import asyncio
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text

from workpal_backend.app import create_app
from workpal_backend.auth.onboarding import update_onboarding
from workpal_backend.auth.service import get_user
from workpal_backend.infrastructure.database import migrate


@pytest.fixture
def mounted(settings):
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    settings.busy_timeout_ms = 80
    migrate(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login = client.post('/auth/verify-code', json={'email': 'dev@workpal.local', 'code': '888888'})
        assert login.status_code == 200
        headers = {'Authorization': 'Bearer ' + login.json()['token']}
        assert client.patch('/api/me/onboarding', headers=headers, json={'questionnaire': {'original': True}}).status_code == 200
        database = app.state.database
        with database.transaction() as session:
            user = get_user(session, client.get('/api/me', headers=headers).json()['id'])
            tables = {name: session.execute(text('SELECT * FROM ' + name)).all()
                      for name in ('workspaces', 'members', 'workspace_invitation')}
        yield app, client, database, headers, user, tables


def unchanged(mounted, *, whole_user=True):
    _, _, database, _, user, tables = mounted
    with database.transaction() as session:
        actual = get_user(session, user['id'])
        if whole_user:
            assert actual == user
        else:
            assert actual['onboarded_at'] == user['onboarded_at']
        assert session.execute(text('SELECT count(*) FROM outbox')).scalar_one() == 0
        for name, rows in tables.items():
            assert session.execute(text('SELECT * FROM ' + name)).all() == rows


def test_revoked_login_bearer(mounted):
    _, client, _, headers, _, _ = mounted
    assert client.post('/auth/logout', headers=headers).status_code == 200
    response = client.patch('/api/me/onboarding', headers=headers, json={'questionnaire': False})
    assert response.status_code == 401
    unchanged(mounted)


def test_production_busy_response(mounted):
    _, client, database, headers, _, _ = mounted
    with sqlite3.connect(database.settings.database_url.removeprefix('sqlite:///')) as blocker:
        blocker.execute('BEGIN IMMEDIATE')
        try:
            started = time.monotonic()
            response = client.patch('/api/me/onboarding', headers=headers, json={'questionnaire': False})
            elapsed = time.monotonic() - started
        finally:
            blocker.rollback()
    assert response.status_code == 503
    assert response.json() == {'error': 'Database is busy; retry later', 'retryable': True}
    assert response.headers['Retry-After'] == '1'
    assert .04 <= elapsed < 2
    unchanged(mounted)


def test_actual_update_fault(mounted):
    _, client, database, headers, _, _ = mounted
    with database.transaction() as session:
        session.execute(text("CREATE TRIGGER onboarding_fault BEFORE UPDATE ON users BEGIN SELECT RAISE(ABORT, 'onboarding fault'); END"))
    response = client.patch('/api/me/onboarding', headers=headers, json={'questionnaire': False})
    assert response.status_code == 500
    assert response.json() == {'error': 'failed to update onboarding'}
    unchanged(mounted)


def test_caught_post_write_failure_then_commit(mounted):
    _, _, database, _, user, _ = mounted
    reached = []
    def fail(conn, cursor, statement, parameters, context, many):
        if statement.lstrip().upper().startswith('UPDATE USERS'):
            reached.append(True)
            raise RuntimeError('post-write')
    with database.transaction() as session:
        event.listen(database.engine, 'after_cursor_execute', fail)
        try:
            with pytest.raises(RuntimeError, match='post-write'):
                update_onboarding(session, user['id'], {'questionnaire': False})
        finally:
            event.remove(database.engine, 'after_cursor_execute', fail)
        session.execute(text('CREATE TABLE unrelated_onboarding (value TEXT)'))
        session.execute(text("INSERT INTO unrelated_onboarding VALUES ('committed')"))
    assert reached == [True]
    unchanged(mounted)
    with database.transaction() as session:
        assert session.execute(text('SELECT value FROM unrelated_onboarding')).scalar_one() == 'committed'


@pytest.mark.parametrize('prefix,status', [(b'{"questionnaire":false}', 200), (b' ' * 16383 + b'{}', 400)])
def test_receive_stops_at_cap(mounted, prefix, status):
    app, _, _, headers, _, _ = mounted
    payload = prefix + b'x' * 40000
    chunks = [payload[i:i + 1024] for i in range(0, len(payload), 1024)]
    received, sent = [], []
    async def run():
        async def receive():
            index = len(received)
            assert index < 16, 'application read beyond the bounded buffer'
            received.append(chunks[index])
            return {'type': 'http.request', 'body': chunks[index], 'more_body': True}
        async def send(message):
            sent.append(message)
        await app({'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1',
                   'method': 'PATCH', 'scheme': 'http', 'path': '/api/me/onboarding',
                   'raw_path': b'/api/me/onboarding', 'query_string': b'',
                   'headers': [(b'authorization', headers['Authorization'].encode())],
                   'client': ('127.0.0.1', 1234), 'server': ('testserver', 80)}, receive, send)
    asyncio.run(run())
    assert len(received) == 16
    assert sum(map(len, received)) == 16384
    assert next(m for m in sent if m['type'] == 'http.response.start')['status'] == status
    unchanged(mounted, whole_user=status != 200)
    if status == 200:
        with mounted[2].transaction() as session:
            assert get_user(session, mounted[4]['id'])['onboarding_questionnaire'] is False
