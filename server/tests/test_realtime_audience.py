"""Real /ws audience tests; direct Hub publish, not Redis/browser acceptance."""
import json
import time
from contextlib import contextmanager

import anyio
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from workpal_backend.app import create_app
from workpal_backend.auth.models import users
from workpal_backend.auth.sessions import revoke_session
from workpal_backend.auth.tokens import issue_session
from workpal_backend.infrastructure.database import migrate
from workpal_backend.workspaces.models import members
from workpal_backend.workspaces.service import create_workspace


@pytest.fixture
def audience(settings):
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    migrate(settings)
    app = create_app(settings)
    identities = []
    with TestClient(app) as client:
        for index in range(2):
            uid = f'00000000-0000-0000-0000-{index+1:012x}'
            email = f'audience-{index}@example.com'
            with app.state.database.transaction() as session:
                session.execute(users.insert().values(id=uid, email=email, name=uid,
                    created_at='2026-01-01', updated_at='2026-01-01'))
                workspace = create_workspace(session, uid, uid, f'audience-{index}')
            token = issue_session(uid, email, uid, settings.auth_secret, 60)
            identities.append((uid, email, workspace, token))
        yield client, app, settings, identities
        assert not app.state.realtime.connections


def receive(ws, seconds=2):
    # Bound the real TestClient receive on its own event-loop portal.
    async def bounded():
        with anyio.fail_after(seconds):
            return await ws._send_rx.receive()
    return ws.portal.call(bounded)


def pong(ws):
    ws.send_json({'type': 'ping'})
    assert receive(ws) == {'type': 'websocket.send', 'text': '{"type":"pong"}'}


@contextmanager
def connected(client, app, identity, token=None):
    client.cookies.clear()
    with client.websocket_connect('/ws?workspace_id=' + identity[2]['id']) as ws:
        ws.send_json({'type': 'auth', 'payload': {'token': token or identity[3]}})
        assert json.loads(receive(ws)['text']) == {'type': 'auth_ack'}
        yield ws
    assert not app.state.realtime.connections


def event(identity):
    return {'type': 'workspace:updated', 'workspaceID': identity[2]['id'],
            'actorID': identity[0], 'actorType': 'user',
            'payload': {'workspace': identity[2]}}


def test_idle_membership_removal_is_enforced_on_next_content_write(audience):
    client, app, settings, identities = audience
    identity = identities[0]
    with connected(client, app, identity) as ws:
        pong(ws)
        with app.state.database.transaction() as session:
            session.execute(delete(members).where(members.c.user_id == identity[0]))
        # Go readPump does not poll membership. A database-only change leaves
        # an idle connection open until a content write or removal event.
        ws.portal.call(anyio.sleep, .65)
        assert app.state.realtime.connections
        ws.send_json({'type':'ping'})
        assert receive(ws) == {'type': 'websocket.close', 'code': 1008, 'reason': ''}


def test_real_expiry_after_handshake_keeps_connection(audience):
    client, app, settings, identities = audience
    identity = identities[0]
    token = issue_session(identity[0], identity[1], identity[0], settings.auth_secret, 2)
    with connected(client, app, identity, token) as ws:
        pong(ws)
        time.sleep(2.1)
        pong(ws)


def test_simultaneous_workspace_audiences(audience):
    client, app, settings, identities = audience
    client.cookies.clear()
    with client.websocket_connect('/ws?workspace_id=' + identities[0][2]['id']) as first:
        first.send_json({'type': 'auth', 'payload': {'token': identities[0][3]}})
        assert json.loads(receive(first)['text']) == {'type': 'auth_ack'}
        with client.websocket_connect('/ws?workspace_id=' + identities[1][2]['id']) as second:
            second.send_json({'type': 'auth', 'payload': {'token': identities[1][3]}})
            assert json.loads(receive(second)['text']) == {'type': 'auth_ack'}
            for identity, target, foreign in [(identities[0], first, second), (identities[1], second, first)]:
                envelope = event(identity)
                client.portal.call(app.state.realtime.publish, envelope)
                assert json.loads(receive(target)['text']) == {
                    'type': envelope['type'], 'payload': envelope['payload'],
                    'actor_id': identity[0], 'actor_type': 'user'}
                pong(foreign)  # FIFO marker proves no foreign event preceded this pong.
        assert len(app.state.realtime.connections) == 1
    assert not app.state.realtime.connections


@pytest.mark.parametrize('invalidate', ['remove', 'revoke'])
def test_invalidation_before_publish_drops_content(audience, invalidate):
    client, app, settings, identities = audience
    identity = identities[0]
    with connected(client, app, identity) as ws:
        pong(ws)
        with app.state.database.transaction() as session:
            if invalidate == 'remove':
                session.execute(delete(members).where(members.c.user_id == identity[0]))
            else:
                revoke_session(session, settings, identity[3])
        client.portal.call(app.state.realtime.publish, event(identity))
        if invalidate == 'remove':
            assert receive(ws) == {'type': 'websocket.close', 'code': 1008, 'reason': ''}
        else:
            assert json.loads(receive(ws)['text'])['type'] == 'workspace:updated'
            pong(ws)
