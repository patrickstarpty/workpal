from fastapi.testclient import TestClient
from workpal_backend.app import create_app
from workpal_backend.infrastructure.database import migrate
from workpal_backend.auth.tokens import issue_session, decode_session
import time

def test_refresh_and_safe_renewal(settings):
    settings.dev_auth = True
    settings.auth_secret = 's'*32
    settings.auth_token_ttl = 60
    migrate(settings)
    with TestClient(create_app(settings)) as c:
        login = c.post('/auth/verify-code', json={'email':'dev@workpal.local','code':'888888'}).json()
        user = login['user']
        fresh = c.post('/api/auth/refresh', headers={'Authorization':'Bearer '+login['token']})
        assert fresh.status_code == 200
        assert fresh.json()['renewed'] is False
        assert fresh.json()['check_again_in_seconds'] == 6
        old = issue_session(user['id'],user['email'],user['name'],settings.auth_secret,60,now=int(time.time())-31,sid=decode_session(login['token'],settings.auth_secret)['sid'])
        c.cookies.set('workpal_auth',old,domain='testserver.local',path='/')
        csrf = c.cookies['workpal_csrf_session']
        r = c.get('/api/me')
        assert r.status_code == 200
        renewed = c.cookies['workpal_auth']
        assert renewed != old
        assert decode_session(renewed,settings.auth_secret)['sid'] == decode_session(old,settings.auth_secret)['sid']
        assert c.post('/api/auth/refresh',headers={'X-CSRF-Token':csrf}).status_code == 200

def test_duration_and_domain(settings):
    from workpal_backend.config import Settings
    for raw, expected in [('1h30m',5400),('1s',60),('bad',2592000),('0',2592000)]:
        assert Settings(database_url=settings.database_url,auth_token_ttl=raw).auth_token_ttl == expected
    assert Settings(database_url=settings.database_url,cookie_domain=' .127.0.0.1 ').cookie_domain == ''
