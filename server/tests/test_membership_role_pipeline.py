"""Actual role PATCH through committed outbox, Redis and the running WS consumer."""
import json
from contextlib import ExitStack
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from test_invitation_realtime_pipeline import handled
from test_realtime_audience import receive, pong
from workpal_backend.app import create_app
from workpal_backend.auth.models import users
from workpal_backend.auth.sessions import revoke_session
from workpal_backend.auth.tokens import issue_session
from workpal_backend.infrastructure.database import migrate
from workpal_backend.infrastructure.delivery import OutboxDelivery
from workpal_backend.infrastructure.outbox import outbox
from workpal_backend.workspaces.models import members
from workpal_backend.workspaces.service import create_workspace


@pytest.mark.parametrize('mode', ['normal', 'revoke_session', 'remove_membership'])
def test_membership_role_pipeline(settings, mode, isolated_relay_redis_port):
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    settings.redis_url = f'redis://127.0.0.1:{isolated_relay_redis_port}'
    settings.redis_key_prefix = 'test:member-role:' + uuid4().hex + ':'
    migrate(settings)
    app = create_app(settings)
    delivery = OutboxDelivery(settings)
    try:
        with TestClient(app) as client, ExitStack() as stack:
            identities = []
            with app.state.database.transaction() as s:
                for label in ['owner', 'target', 'stranger']:
                    uid = str(uuid4())
                    email = label + '@example.com'
                    s.execute(users.insert().values(id=uid, email=email, name=label,
                        created_at='2026-01-01', updated_at='2026-01-01'))
                    workspace = create_workspace(s, uid, label, label)
                    identities.append((uid, workspace['id'],
                        issue_session(uid, email, label, settings.auth_secret, 60)))
                owner, target, stranger = identities
                member_id = str(uuid4())
                s.execute(members.insert().values(id=member_id, workspace_id=owner[1],
                    user_id=target[0], role='admin', created_at='2026-01-01'))
            def connect(identity, workspace):
                ws = stack.enter_context(client.websocket_connect('/ws?workspace_id=' + workspace))
                ws.send_json({'type': 'auth', 'payload': {'token': identity[2]}})
                assert json.loads(receive(ws)['text']) == {'type': 'auth_ack'}
                return ws
            sockets = [connect(owner, owner[1]), connect(target, owner[1]),
                connect(target, target[1]), connect(stranger, stranger[1])]
            url = '/api/workspaces/' + owner[1] + '/members/' + member_id
            def patch(identity, role):
                return client.patch(url, headers={'Authorization': 'Bearer ' + identity[2]},
                    json={'role': role})
            def snapshot():
                with app.state.database.transaction() as s:
                    return (s.scalar(select(members.c.role).where(members.c.id == member_id)),
                        list(s.scalars(select(outbox.c.envelope))))
            before = snapshot()
            assert patch(stranger, 'member').status_code == 404
            assert snapshot() == before
            response = patch(owner, 'member')
            assert response.status_code == 200, response.text
            role, raw = snapshot()
            assert role == 'member'
            assert len(raw) == 1
            event = json.loads(raw[0])
            assert event['type'] == 'member:updated'
            assert event['workspaceID'] == owner[1]
            assert event['actorID'] == owner[0]
            assert event['actorType'] == 'member'
            assert event['payload'] == {'member': response.json()}
            # The already authenticated former admin must lose HTTP privilege immediately.
            before = snapshot()
            assert patch(target, 'admin').status_code == 403
            assert snapshot() == before
            if mode != 'normal':
                with app.state.database.transaction() as s:
                    if mode == 'revoke_session':
                        revoke_session(s, settings, target[2])
                    else:
                        s.execute(delete(members).where(members.c.id == member_id))
            assert delivery.dispatch(app.state.database) == 1
            handled(app, event, delivery.client.xrevrange(delivery.channel, count=1)[0][0])
            expected = dict(type='member:updated', payload={'member': response.json()},
                actor_id=owner[0], actor_type='member')
            closed = {1} if mode == 'remove_membership' else set()
            for index, ws in enumerate(sockets):
                if index in closed:
                    assert receive(ws) == {'type': 'websocket.close', 'code': 1008, 'reason': ''}
                else:
                    if index in [0, 1]:
                        assert json.loads(receive(ws)['text']) == expected
                    pong(ws)
            duplicate = delivery.client.xadd(delivery.channel, {'envelope': json.dumps(event)})
            handled(app, event, duplicate)
            for index, ws in enumerate(sockets):
                if index not in closed:
                    pong(ws)
    finally:
        delivery.client.delete(delivery.channel)
        delivery.close()
