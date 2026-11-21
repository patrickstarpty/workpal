from fastapi.testclient import TestClient
from workpal_backend.app import create_app
from workpal_backend.infrastructure.database import migrate
from workpal_backend.auth.tokens import decode_session, issue_session


def test_logout_revokes_sid_persistently(settings):
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    migrate(settings)
    with TestClient(create_app(settings)) as client:
        login = client.post('/auth/verify-code', json={'email': 'dev@workpal.local', 'code': '888888'}).json()
        token, user = login['token'], login['user']
        sid = decode_session(token, settings.auth_secret)['sid']
        renewed = issue_session(user['id'], user['email'], user['name'], settings.auth_secret, settings.auth_token_ttl, sid=sid)
        other = issue_session(user['id'], user['email'], user['name'], settings.auth_secret, 60)
        assert client.post('/auth/logout').status_code == 200
        for copied in (token, renewed):
            assert client.get('/api/me', headers={'Authorization': 'bEaReR ' + copied}).status_code == 401
        client.cookies.set('workpal_auth', token)
        assert client.get('/api/me').status_code == 401
        assert client.post('/api/auth/refresh', headers={'Authorization': 'Bearer ' + renewed}).status_code == 401
        assert client.post('/auth/logout').status_code == 200
    with TestClient(create_app(settings)) as client:
        assert client.get('/api/me', headers={'Authorization': 'Bearer ' + token}).status_code == 401
        assert client.get('/api/me', headers={'Authorization': 'Bearer ' + other}).status_code == 200


def test_invalid_logout_and_busy_failure(settings):
    import sqlite3
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    migrate(settings)
    with TestClient(create_app(settings)) as client:
        for token in ('forged', issue_session('missing', 'x', 'x', settings.auth_secret, 1, now=1)):
            result = client.post('/auth/logout', headers={'Authorization': 'Bearer ' + token})
            assert result.status_code == 200
        token = client.post('/auth/verify-code', json={'email': 'dev@workpal.local', 'code': '888888'}).json()['token']
        connection = sqlite3.connect(settings.database_url.removeprefix('sqlite:///'))
        try:
            connection.execute('BEGIN IMMEDIATE')
            result = client.post('/auth/logout', headers={'Authorization': 'Bearer ' + token})
            assert result.status_code == 503
            assert not result.headers.get_list('set-cookie')
        finally:
            connection.rollback()
            connection.close()
        assert client.get('/api/me', headers={'Authorization': 'Bearer ' + token}).status_code == 200


def test_revocation_during_response_blocks_cookie_renewal(settings):
    from fastapi import Depends, Request
    from workpal_backend.auth.dependencies import require_principal
    from workpal_backend.auth.sessions import revoke_session
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    migrate(settings)
    app = create_app(settings)
    @app.get('/test/revoke-during-response')
    def revoke(request: Request, principal=Depends(require_principal)):
        with app.state.database.transaction() as session:
            revoke_session(session, settings, request.cookies['workpal_auth'])
        return {'private': 'must not escape after failed validation'}
    with TestClient(app) as client:
        client.post('/auth/verify-code', json={'email':'dev@workpal.local','code':'888888'})
        response = client.get('/test/revoke-during-response')
        assert response.status_code == 401
        assert response.json() == {'error': 'Unauthorized'}
        assert not response.headers.get_list('set-cookie')


def test_busy_during_response_renewal_is_retryable(settings, monkeypatch):
    from fastapi import Depends
    from workpal_backend.auth.dependencies import require_principal
    from workpal_backend.auth import sessions
    from workpal_backend.infrastructure.database import DatabaseBusy
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    migrate(settings)
    app = create_app(settings)
    @app.get('/test/busy-during-response')
    def busy_after_auth(principal=Depends(require_principal)):
        def busy(*args): raise DatabaseBusy('locked')
        monkeypatch.setattr(sessions, 'validate_session', busy)
        return {'private': 'must not escape'}
    with TestClient(app) as client:
        client.post('/auth/verify-code', json={'email':'dev@workpal.local','code':'888888'})
        response = client.get('/test/busy-during-response')
        assert response.status_code == 503
        assert response.json()['retryable'] is True
        assert response.headers['retry-after'] == '1'
        assert not response.headers.get_list('set-cookie')
