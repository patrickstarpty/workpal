import pytest
from fastapi.testclient import TestClient
from workpal_backend.app import create_app
from workpal_backend.infrastructure.database import migrate
from starlette.requests import Request
from workpal_backend.auth.token_source import extract_token


@pytest.mark.parametrize(('cookies', 'expected'), [
    ([b'workpal_auth=first; workpal_auth=second'], ('first', True)),
    ([b'workpal_auth=; workpal_auth=second'], ('', False)),
    ([b'workpal_auth=first', b'workpal_auth=second'], ('first', True)),
    ([b'workpal_auth=bad\\value; workpal_auth=valid'], ('valid', True)),
    ([b'workpal_auth=valid;' + b'x=1;' * 2999], ('', False)),
])
def test_http_auth_uses_first_valid_go_cookie(cookies, expected):
    request = Request({'type': 'http', 'headers': [(b'cookie', value) for value in cookies]})
    assert extract_token(request) == expected


@pytest.mark.parametrize('authorization', ['', 'Basic ignored', 'bearer ignored', 'BEARER ignored'])
def test_non_bearer_header_falls_back_to_cookie_and_requires_csrf(settings, authorization):
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    migrate(settings)
    with TestClient(create_app(settings)) as client:
        client.post('/auth/verify-code', json={'email':'dev@workpal.local','code':'888888'})
        headers = {'Authorization':authorization}
        assert client.get('/api/me', headers=headers).status_code == 200
        assert client.post('/api/workspaces', json={'name':'A','slug':'cookie-fallback'}, headers=headers).status_code == 403
        headers['X-CSRF-Token'] = client.cookies['workpal_csrf_session']
        assert client.post('/api/workspaces', json={'name':'A','slug':'cookie-fallback'}, headers=headers).status_code == 201


def test_empty_bearer_does_not_fall_back_to_cookie(settings):
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    migrate(settings)
    with TestClient(create_app(settings)) as client:
        client.post('/auth/verify-code', json={'email':'dev@workpal.local','code':'888888'})
        assert client.get('/api/me', headers={'Authorization':'Bearer '}).status_code == 401
