import pytest
from fastapi.testclient import TestClient
from workpal_backend.app import create_app
from workpal_backend.infrastructure.database import migrate


def test_login(settings):
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    migrate(settings)
    with TestClient(create_app(settings)) as c:
        assert c.get('/api/me').status_code == 401
        assert c.post('/auth/verify-code', json={}).status_code == 400
        assert c.post('/auth/verify-code', json={'email':'dev@workpal.local','code':'wrong'}).status_code == 400
        r = c.post('/auth/verify-code', json={'email':' DEV@workpal.local ','code':' 888888 '})
        assert r.status_code == 200
        uid = r.json()['user']['id']
        assert c.get('/api/me').json()['id'] == uid
        assert c.post('/auth/verify-code', json={'email':'dev@workpal.local','code':'888888'}).json()['user']['id'] == uid
        assert c.get('/api/me', headers={'Authorization':'Bearer forged'}).status_code == 401
        assert c.post('/auth/logout').status_code == 200
        assert c.get('/api/me').status_code == 401
    with TestClient(create_app(settings)) as c:
        assert c.get('/api/me', headers={'Authorization':'Bearer '+r.json()['token']}).json()['id'] == uid


def test_disabled(settings):
    with TestClient(create_app(settings)) as c:
        assert c.get('/api/config').json()['development_auth'] is False
        assert c.post('/auth/send-code', json={'email':'dev@workpal.local'}).status_code == 501
        assert c.get('/health').status_code == 200


def test_security_boundaries(settings):
    from fastapi import Depends
    from workpal_backend.auth.dependencies import require_principal
    from workpal_backend.auth.tokens import issue_session
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    migrate(settings)
    app = create_app(settings)
    @app.post('/test-mutation')
    def mutation(principal=Depends(require_principal)):
        return {'id': principal.user_id}
    with TestClient(app) as c:
        r = c.post('/auth/verify-code', json={'email':'dev@workpal.local','code':'888888'})
        user = r.json()['user']
        cookies = r.headers.get_list('set-cookie')
        assert len(cookies) == 3
        assert all('Path=/' in x and 'SameSite=strict' in x and 'Max-Age=2592000' in x for x in cookies)
        assert 'HttpOnly' in cookies[0]
        assert all('HttpOnly' not in x for x in cookies[1:])
        assert c.post('/test-mutation').status_code == 403
        assert c.post('/test-mutation', headers={'X-CSRF-Token':'bad'}).status_code == 403
        for name in ('workpal_csrf_session','workpal_csrf'):
            assert c.post('/test-mutation', headers={'X-CSRF-Token':c.cookies[name]}).status_code == 200
        assert c.post('/test-mutation', headers={'Authorization':'Bearer '+r.json()['token']}).status_code == 200
        expired = issue_session(user['id'],user['email'],user['name'],settings.auth_secret,60,now=1)
        for token in ('mul_fake','mat_fake','mcn_fake','forged',expired,r.json()['token']+'tamper'):
            assert c.get('/api/me', headers={'Authorization':'Bearer '+token}).status_code == 401
        missing_user = issue_session('unknown',user['email'],user['name'],settings.auth_secret,60)
        assert c.get('/api/me',headers={'Authorization':'Bearer '+missing_user}).status_code == 401
        cleared = c.post('/auth/logout').headers.get_list('set-cookie')
        assert len(cleared) == 3 and all('Max-Age=-1' in x for x in cleared)
        assert c.get('/api/me',headers={'X-Actor-Source':'session','X-User-ID':user['id']}).status_code == 401
        assert c.post('/auth/google').status_code == 501
        assert c.post('/auth/send-code', json={'email':'external@example.com'}).status_code == 501
        assert c.post('/auth/send-code', json={'email':' DEV@workpal.local '}).status_code == 200
        for body in ({}, {'email':None}, {'email':123}):
            response = c.post('/auth/send-code',json=body)
            assert response.status_code == 400 and 'error' in response.json()


def test_auth_configuration(settings):
    from workpal_backend.config import Settings
    values = settings.model_dump()
    for overrides in ({'dev_auth':True,'auth_secret':None}, {'dev_auth':True,'auth_secret':'short'},
                      {'dev_auth':True,'auth_secret':'s'*32,'environment':'production'}):
        with pytest.raises(ValueError):
            Settings(**(values | overrides))


def test_secure_cookies(settings):
    settings.dev_auth = True
    settings.auth_secret = 's'*32
    settings.frontend_origin = 'https://localhost:4173'
    migrate(settings)
    with TestClient(create_app(settings),base_url='https://localhost') as c:
        response = c.post('/auth/verify-code',json={'email':'dev@workpal.local','code':'888888'})
        assert all('Secure' in x for x in response.headers.get_list('set-cookie'))
