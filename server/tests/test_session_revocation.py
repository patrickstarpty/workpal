"""Go auth/session.go is stateless; local legacy revocation rows are preserved."""
from fastapi.testclient import TestClient
from workpal_backend.app import create_app
from workpal_backend.infrastructure.database import migrate


def test_logout_clears_cookies_but_copied_jwt_survives_restart(settings):
    settings.dev_auth=True
    settings.auth_secret='s'*32
    migrate(settings)
    with TestClient(create_app(settings)) as client:
        token=client.post('/auth/verify-code',json={'email':'dev@workpal.local','code':'888888'}).json()['token']
        result=client.post('/auth/logout')
        assert result.status_code==200
        assert len(result.headers.get_list('set-cookie'))==3
        assert client.get('/api/me').status_code==401
        assert client.get('/api/me',headers={'Authorization':'Bearer '+token}).status_code==200
    with TestClient(create_app(settings)) as client:
        assert client.get('/api/me',headers={'Authorization':'Bearer '+token}).status_code==200
        assert client.get('/api/me',headers={'Authorization':'Bearer '+token+'tampered'}).status_code==401


def test_logout_does_not_access_locked_database(settings):
    import sqlite3
    settings.dev_auth=True
    settings.auth_secret='s'*32
    migrate(settings)
    with TestClient(create_app(settings)) as client:
        token=client.post('/auth/verify-code',json={'email':'dev@workpal.local','code':'888888'}).json()['token']
        with sqlite3.connect(settings.database_url.removeprefix('sqlite:///')) as connection:
            connection.execute('BEGIN IMMEDIATE')
            result=client.post('/auth/logout',headers={'Authorization':'Bearer '+token})
            assert result.status_code==200
            assert len(result.headers.get_list('set-cookie'))==3
            connection.rollback()


def test_legacy_revocation_row_is_preserved_but_does_not_gate_go_http_auth(settings):
    from sqlalchemy import text
    from workpal_backend.auth.sessions import revoke_session
    settings.dev_auth=True
    settings.auth_secret='s'*32
    migrate(settings)
    app=create_app(settings)
    with TestClient(app) as client:
        token=client.post('/auth/verify-code',json={'email':'dev@workpal.local','code':'888888'}).json()['token']
        with app.state.database.transaction() as session:revoke_session(session,settings,token)
        assert client.get('/api/me',headers={'Authorization':'Bearer '+token}).status_code==200
        assert client.post('/api/auth/refresh',headers={'Authorization':'Bearer '+token}).status_code==200
        with app.state.database.transaction() as session:
            assert session.scalar(text('SELECT count(*) FROM session_revocations'))==1
