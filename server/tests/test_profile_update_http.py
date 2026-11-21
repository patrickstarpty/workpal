from fastapi.testclient import TestClient
from workpal_backend.app import create_app
from workpal_backend.infrastructure.database import migrate


def test_profile_persistence_and_rejections(settings):
    settings.dev_auth = True
    settings.auth_secret = 's'*32
    migrate(settings)
    with TestClient(create_app(settings)) as c:
        login = c.post('/auth/verify-code', json={'email':'dev@workpal.local','code':'888888'}).json()
        headers = {'Authorization':'Bearer '+login['token']}
        r = c.patch('/api/me', json={'name':' Ada ', 'language':'fr', 'timezone':'Local', 'profile_description':'猫'*2000}, headers=headers)
        assert r.status_code == 200
        original = r.json()
        assert original['name'] == 'Ada'
        for body, status, error in [({'name':' ', 'avatar_url':'new'},400,'name is required'), ({'name':'Changed','avatar_url':'new'},501,'Avatar updates are not supported'), ({'language':'bad','timezone':'bad'},400,'unsupported language'), ({'profile_description':'猫'*2001},400,'profile_description exceeds 2000 characters'), ({'timezone':'No/Such'},400,'invalid timezone')]:
            r = c.patch('/api/me', json=body, headers=headers)
            assert (r.status_code,r.json()['error']) == (status,error)
            assert c.get('/api/me',headers=headers).json() == original
        assert c.patch('/api/me',json={},headers=headers).json()['updated_at'] != original['updated_at']
        assert c.patch('/api/me',json={'name':None,'timezone':''},headers=headers).json()['timezone'] is None
        assert c.patch('/api/me',json={}).status_code == 403
        assert c.patch('/api/me',json={},headers={'X-CSRF-Token':c.cookies['workpal_csrf_session']}).status_code == 200
        c.post('/auth/logout',headers=headers)
        assert c.patch('/api/me',json={},headers=headers).status_code == 401
    with TestClient(create_app(settings)) as c:
        login = c.post('/auth/verify-code',json={'email':'dev@workpal.local','code':'888888'}).json()
        assert c.get('/api/me',headers={'Authorization':'Bearer '+login['token']}).json()['name'] == 'Ada'


def test_contract_fixtures(settings):
    import json
    from pathlib import Path
    settings.dev_auth = True
    settings.auth_secret = 's'*32
    migrate(settings)
    fixtures = json.loads((Path(__file__).parents[1]/'contracts/batches/profile-update.json').read_text())
    with TestClient(create_app(settings)) as c:
        token = c.post('/auth/verify-code',json={'email':'dev@workpal.local','code':'888888'}).json()['token']
        for fixture in fixtures['fixtures']:
            r = c.patch('/api/me',content=fixture['raw_body'],headers={'Authorization':'Bearer '+token})
            assert r.status_code == fixture['status'], fixture
            if fixture['error']:
                assert r.json() == {'error':fixture['error']}
            else:
                assert set(r.json()) == set(fixtures['response_fields'])


def test_profile_respects_outer_transaction_rollback(settings):
    import pytest
    from workpal_backend.infrastructure.database import Database
    from workpal_backend.auth.service import get_or_create_development_user, get_user
    from workpal_backend.auth.profile import update_profile
    migrate(settings)
    db = Database(settings)
    try:
        with db.transaction() as session:
            original = get_or_create_development_user(session, 'dev@workpal.local')
        with pytest.raises(RuntimeError, match='caller abort'):
            with db.transaction() as session:
                update_profile(session, original['id'], {'name': 'Must rollback'}, ['load'])
                raise RuntimeError('caller abort')
        with db.transaction() as session:
            assert get_user(session, original['id']) == original
    finally:
        db.close()
