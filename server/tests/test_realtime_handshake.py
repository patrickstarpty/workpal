"""Real HTTP upgrade regressions with persisted users and disposable SQLite."""
import time

import anyio
import pytest
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketDenialResponse

from workpal_backend.app import create_app
from workpal_backend.auth.tokens import issue_session
from workpal_backend.infrastructure.database import migrate


@pytest.fixture
def handshake(settings):
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    settings.frontend_origin = 'https://frontend.example'
    migrate(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        response = client.post('/auth/verify-code', json={'email': 'dev@workpal.local', 'code': '888888'})
        assert response.status_code == 200
        login = response.json()
        response = client.post('/api/workspaces', headers={'Authorization': 'Bearer ' + login['token']},
                               json={'name': 'Handshake', 'slug': 'handshake', 'issue_prefix': 'HS'})
        assert response.status_code == 201
        yield client, login, response.json()


def denied(client, path, status, message, headers=None):
    # Bound the actual ASGI handshake, including accidental first-frame waits.
    def exercise():
        with pytest.raises(WebSocketDenialResponse) as error:
            with client.websocket_connect(path, headers={'cookie': 'workpal_auth=' + client.cookies.get('workpal_auth', ''), **(headers or {})}):
                pytest.fail('WebSocket unexpectedly accepted')
        assert error.value.status_code == status
        assert error.value.json() == {'error': message}
    async def connect():
        with anyio.fail_after(3):
            await anyio.to_thread.run_sync(exercise, abandon_on_cancel=True)
    client.portal.call(connect)


@pytest.mark.parametrize('credential', ['invalid', 'expired', 'revoked'])
def test_cookie_credentials_rejected_before_upgrade(handshake, settings, credential):
    client, login, workspace = handshake
    token = login['token']
    if credential == 'invalid':
        token = 'invalid.signature.cookie'
    elif credential == 'expired':
        user = login['user']
        token = issue_session(user['id'], user['email'], user['name'], settings.auth_secret,
                              1, now=time.time() - 60)
    else:
        assert client.post('/auth/logout', headers={'Authorization': 'Bearer ' + token}).status_code == 200
    client.cookies.clear()
    client.cookies.set('workpal_auth', token)
    denied(client, '/ws?workspace_slug=handshake', 401, 'Unauthorized; PAT authentication unsupported')


def test_valid_persisted_nonmember_is_forbidden(handshake):
    client, login, workspace = handshake
    from sqlalchemy import delete
    from workpal_backend.workspaces.models import members
    with client.app.state.database.transaction() as session:
        session.execute(delete(members).where(members.c.workspace_id == workspace['id'],
                                               members.c.user_id == login['user']['id']))
    denied(client, '/ws?workspace_slug=handshake', 403, 'Forbidden')


@pytest.mark.parametrize(('path', 'status', 'message'), [
    ('/ws', 400, 'Workspace required'),
    ('/ws?workspace_slug=does-not-exist', 404, 'Workspace not found'),
])
def test_workspace_resolution_denials(handshake, path, status, message):
    denied(handshake[0], path, status, message)


@pytest.mark.parametrize('origin', ['https://frontend.example', 'http://testserver'])
def test_allowed_origins_and_workspace_id_precedence(handshake, origin):
    client, login, workspace = handshake
    def exercise():
        with client.websocket_connect('/ws?workspace_id=' + workspace['id'] + '&workspace_slug=does-not-exist',
                                      headers={'origin': origin, 'cookie': 'workpal_auth=' + login['token']}) as ws:
            ws.send_json({'type': 'ping'})
            assert ws.receive_json() == {'type': 'pong'}
    async def connect():
        with anyio.fail_after(3):
            await anyio.to_thread.run_sync(exercise, abandon_on_cancel=True)
    client.portal.call(connect)


def test_forwarded_origin_spoof_is_forbidden(handshake):
    denied(handshake[0], '/ws?workspace_slug=handshake', 403, 'Forbidden origin',
           {'origin': 'https://spoof.example', 'x-forwarded-host': 'spoof.example',
            'x-forwarded-proto': 'https'})
