import pytest
from fastapi.testclient import TestClient
from workpal_backend.app import create_app
from workpal_backend.infrastructure.database import migrate


def test_completion(settings):
    settings.dev_auth = True
    settings.auth_secret = 's'*32
    migrate(settings)
    with TestClient(create_app(settings)) as c:
        token = c.post('/auth/verify-code',json={'email':'dev@workpal.local','code':'888888'}).json()['token']
        h = {'Authorization':'Bearer '+token}
        url = '/api/me/onboarding/complete'
        first = c.post(url, headers=h)
        assert first.status_code == 200
        stamp = first.json()['onboarded_at']
        assert stamp
        for raw in ['', ' ', 'null', '{} trailing', '{"WORKSPACE_ID":"11111111-1111-4111-8111-111111111111"}', '{"completion_path":"x","completion_path":null}']:
            r = c.post(url,content=raw,headers=h)
            assert r.status_code == 200
            assert r.json()['onboarded_at'] == stamp
        for raw, status in [('{',400),('[]',400),('{"completion_path":1,"completion_path":"ok"}',400),('{"workspace_id":"bad"}',400),(' '*16384,200),(' '*16385,413)]:
            assert c.post(url,content=raw,headers=h).status_code == status
        assert c.post(url).status_code == 403
        assert c.post(url,headers={'X-CSRF-Token':c.cookies['workpal_csrf_session']}).status_code == 200
    with TestClient(create_app(settings)) as c:
        assert c.post(url).status_code == 401
        assert c.post(url,headers=h).json()['onboarded_at'] == stamp


def test_atomic_faults_and_concurrency(settings):
    from concurrent.futures import ThreadPoolExecutor
    from sqlalchemy import text
    from fastapi import HTTPException
    from workpal_backend.infrastructure.database import Database
    from workpal_backend.auth.service import get_or_create_development_user, get_user
    from workpal_backend.auth.completion import complete_onboarding
    from workpal_backend.auth.completion_routes import persist
    migrate(settings)
    db = Database(settings)
    try:
        with db.transaction() as s:
            original = get_or_create_development_user(s,'dev@workpal.local')
        uid = original['id']
        with pytest.raises(RuntimeError):
            with db.transaction() as s:
                complete_onboarding(s, uid)
                raise RuntimeError('outer rollback')
        with db.transaction() as s:
            assert get_user(s,uid) == original
            s.execute(text("CREATE TRIGGER fail_completion AFTER UPDATE ON users BEGIN SELECT RAISE(FAIL, 'actual SQL fault'); END"))
        from sqlalchemy.exc import SQLAlchemyError
        with db.transaction() as s:
            with pytest.raises(SQLAlchemyError):
                complete_onboarding(s,uid)
            assert get_user(s,uid) == original
        with pytest.raises(HTTPException) as fault:
            persist(db,uid)
        assert (fault.value.status_code,fault.value.detail) == (500,'failed to complete onboarding')
        with db.transaction() as s:
            s.execute(text('DROP TRIGGER fail_completion'))
        with pytest.raises(HTTPException) as missing:
            persist(db,'missing')
        assert missing.value.detail == 'failed to complete onboarding'
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: persist(db,uid), range(4)))
        assert len({r['onboarded_at'] for r in results}) == 1
        with db.transaction() as s:
            for table in ('workspaces', 'members', 'workspace_invitation', 'outbox'):
                assert s.execute(text('SELECT count(*) FROM '+table)).scalar_one() == 0
    finally:
        db.close()


def test_exact_response_revocation_and_unknown_length(settings):
    import json
    from decimal import Decimal
    settings.dev_auth = True
    settings.auth_secret = 's'*32
    migrate(settings)
    with TestClient(create_app(settings)) as c:
        token = c.post('/auth/verify-code',json={'email':'dev@workpal.local','code':'888888'}).json()['token']
        h = {'Authorization':'Bearer '+token}
        c.patch('/api/me/onboarding',content='{"questionnaire":{"n":12345678901234567890.123456789}}',headers=h)
        url = '/api/me/onboarding/complete'
        r = c.post(url,headers=h,content=iter([b'invalid unknown length']))
        assert r.status_code == 200
        assert json.loads(r.text,parse_float=Decimal)['onboarding_questionnaire']['n'] == Decimal('12345678901234567890.123456789')
        assert c.post(url,headers=h,content=iter([b'x'*8192,b'x'*8193])).status_code == 413
        assert c.post('/auth/logout',headers=h).status_code in (200,204)
        assert c.post(url,headers=h).status_code == 401


@pytest.mark.parametrize('failure', ['busy', 'sql'])
def test_completion_mounted_database_failures(settings, failure):
    import sqlite3
    import time
    from sqlalchemy import text
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    settings.busy_timeout_ms = 80
    migrate(settings)
    with TestClient(create_app(settings)) as client:
        token = client.post('/auth/verify-code', json={'email': 'dev@workpal.local', 'code': '888888'}).json()['token']
        headers = {'Authorization': 'Bearer ' + token}
        before = client.get('/api/me', headers=headers).json()
        database = client.app.state.database
        if failure == 'sql':
            with database.transaction() as session:
                session.execute(text("CREATE TRIGGER reject_completion AFTER UPDATE ON users BEGIN SELECT RAISE(FAIL, 'completion failure'); END"))
            response = client.post('/api/me/onboarding/complete', headers=headers)
            assert response.status_code == 500
            assert response.json() == {'error': 'failed to complete onboarding'}
        else:
            with sqlite3.connect(settings.database_url.removeprefix('sqlite:///')) as blocker:
                blocker.execute('BEGIN IMMEDIATE')
                try:
                    start = time.monotonic()
                    response = client.post('/api/me/onboarding/complete', headers=headers)
                    elapsed = time.monotonic() - start
                finally:
                    blocker.rollback()
            assert response.status_code == 503
            assert response.json() == {'error': 'Database is busy; retry later', 'retryable': True}
            assert response.headers['Retry-After'] == '1'
            assert .04 <= elapsed < 2
        assert client.get('/api/me', headers=headers).json() == before
        with database.transaction() as session:
            for table in ('workspaces', 'members', 'workspace_invitation', 'outbox'):
                assert session.execute(text('SELECT count(*) FROM ' + table)).scalar_one() == 0
