"""Profile failures through the mounted production HTTP application."""
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text

from workpal_backend.app import create_app
from workpal_backend.auth.service import get_user
from workpal_backend.infrastructure.database import migrate


@pytest.fixture
def profile_http(settings):
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    settings.busy_timeout_ms = 80
    migrate(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login = client.post('/auth/verify-code', json={'email': 'dev@workpal.local', 'code': '888888'})
        assert login.status_code == 200
        headers = {'Authorization': 'Bearer ' + login.json()['token']}
        original = client.get('/api/me', headers=headers).json()
        with app.state.database.transaction() as session:
            original = get_user(session, original['id'])
        yield client, app.state.database, headers, original


def assert_unchanged(database, original):
    with database.transaction() as session:
        assert get_user(session, original['id']) == original
        assert session.execute(text('SELECT count(*) FROM outbox')).scalar_one() == 0


@pytest.mark.parametrize('phase,status,message', [
    ('load', 404, 'user not found'),
    ('update', 500, 'failed to update user'),
])
def test_mounted_profile_sql_failure(profile_http, phase, status, message):
    client, database, headers, original = profile_http
    reached = {'savepoint': False, 'fault': False}

    def fail(conn, cursor, statement, parameters, context, executemany):
        sql = statement.lstrip().upper()
        if sql.startswith('SAVEPOINT'):
            conn.info['profile_failure_savepoint'] = True
            reached['savepoint'] = True
        if not conn.info.get('profile_failure_savepoint'):
            return
        target = (phase == 'load' and sql.startswith('SELECT') and 'FROM USERS' in sql) or (
            phase == 'update' and sql.startswith('UPDATE USERS'))
        if target:
            reached['fault'] = True
            cursor.execute('SELECT * FROM missing_profile_http_failure_table')

    event.listen(database.engine, 'before_cursor_execute', fail)
    try:
        response = client.patch('/api/me', headers=headers, json={'name': 'Changed'})
    finally:
        event.remove(database.engine, 'before_cursor_execute', fail)
    assert reached == {'savepoint': True, 'fault': True}
    assert response.status_code == status
    assert response.json() == {'error': message}
    assert 'retry-after' not in response.headers
    assert_unchanged(database, original)


def test_mounted_profile_sqlite_lock(profile_http):
    client, database, headers, original = profile_http
    path = database.settings.database_url.removeprefix('sqlite:///')
    with sqlite3.connect(path) as blocker:
        blocker.execute('BEGIN IMMEDIATE')
        try:
            started = time.monotonic()
            response = client.patch('/api/me', headers=headers, json={'name': 'Changed'})
            elapsed = time.monotonic() - started
        finally:
            blocker.rollback()
    assert response.status_code == 503
    assert response.json() == {'error': 'Database is busy; retry later', 'retryable': True}
    assert response.headers['Retry-After'] == '1'
    assert 0.04 <= elapsed < 2
    assert_unchanged(database, original)
