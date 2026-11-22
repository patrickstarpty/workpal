import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from workpal_backend.app import create_app
from workpal_backend.infrastructure.database import migrate

def test_onboarding_http(settings):
    settings.dev_auth = True
    settings.auth_secret = 's'*32
    migrate(settings)
    with TestClient(create_app(settings)) as c:
        token = c.post('/auth/verify-code', json={'email':'dev@workpal.local','code':'888888'}).json()['token']
        headers = {'Authorization':'Bearer '+token}
        original = c.get('/api/me', headers=headers).json()
        fixtures = json.loads((Path(__file__).parents[1]/'contracts/batches/onboarding.json').read_text())
        for fixture in fixtures['fixtures']:
            r = c.patch('/api/me/onboarding', content=fixture['raw_body'], headers=headers)
            assert r.status_code == fixture['status'], fixture
            if fixture['error']:
                assert r.json() == {'error':fixture['error']}
            else:
                assert set(r.json()) == set(original)
        for raw, expected in [
            ('{"questionnaire":{"old":true}}', {'old':True}),
            ('{"questionnaire":{"new":1}}', {'new':1}),
            ('{"QUESTIONNAIRE":false}', False),
            ('{"questionnaire":[]}', []),
            ('{"questionnaire":42}', 42),
            ('{"questionnaire":{},"questionnaire":null}', 42),
            ('null',42), ('{}',42)]:
            result = c.patch('/api/me/onboarding', content=raw, headers=headers).json()
            assert result['onboarding_questionnaire'] == expected
            for key in original.keys()-{'updated_at','onboarding_questionnaire'}:
                assert result[key] == original[key]
        for raw, status in [(' '*16382+'{}',200),(' '*16383+'{}',400),('{}'+'x'*20000,200),('{"questionnaire":NaN}',400),('{"questionnaire":Infinity}',400)]:
            assert c.patch('/api/me/onboarding',content=raw,headers=headers).status_code == status
        assert c.patch('/api/me/onboarding',json={}).status_code == 403
        assert c.patch('/api/me/onboarding',json={},headers={'X-CSRF-Token':c.cookies['workpal_csrf_session']}).status_code == 200
    with TestClient(create_app(settings)) as c:
        assert c.patch('/api/me/onboarding',json={}).status_code == 401
        token = c.post('/auth/verify-code',json={'email':'dev@workpal.local','code':'888888'}).json()['token']
        assert c.get('/api/me',headers={'Authorization':'Bearer '+token}).json()['onboarding_questionnaire'] == 42

def test_caller_rollback(settings):
    from workpal_backend.infrastructure.database import Database
    from workpal_backend.auth.service import get_or_create_development_user, get_user
    from workpal_backend.auth.onboarding import update_onboarding
    migrate(settings)
    db = Database(settings)
    try:
        with db.transaction() as s:
            original = get_or_create_development_user(s,'dev@workpal.local')
        with pytest.raises(RuntimeError):
            with db.transaction() as s:
                update_onboarding(s,original['id'],{'questionnaire':False})
                raise RuntimeError('abort')
        with db.transaction() as s:
            assert get_user(s,original['id']) == original
    finally:
        db.close()

def test_sql_error_and_missing_row(settings):
    from sqlalchemy import text
    from workpal_backend.infrastructure.database import Database
    from workpal_backend.auth.service import get_or_create_development_user
    from workpal_backend.auth.onboarding_routes import persist
    from fastapi import HTTPException
    migrate(settings)
    db = Database(settings)
    try:
        with pytest.raises(HTTPException) as missing:
            persist(db,'missing',{})
        assert (missing.value.status_code,missing.value.detail) == (500,'failed to update onboarding')
        with db.transaction() as s:
            user = get_or_create_development_user(s,'dev@workpal.local')
            s.execute(text("CREATE TRIGGER fail_onboarding BEFORE UPDATE ON users BEGIN SELECT RAISE(ABORT, 'failure'); END"))
        with pytest.raises(HTTPException) as failed:
            persist(db,user['id'],{})
        assert (failed.value.status_code,failed.value.detail) == (500,'failed to update onboarding')
    finally:
        db.close()
