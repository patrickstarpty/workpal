"""Finite conclusion coverage through HTTP, committed outbox, Redis and real /ws."""
import json
from contextlib import ExitStack
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from test_invitation_realtime_pipeline import handled
from test_realtime_audience import receive, pong
from workpal_backend.app import create_app
from workpal_backend.auth.models import users
from workpal_backend.auth.sessions import revoke_session
from workpal_backend.auth.tokens import issue_session
from workpal_backend.infrastructure.database import migrate
from workpal_backend.infrastructure.delivery import OutboxDelivery
from workpal_backend.infrastructure.outbox import outbox
from workpal_backend.workspaces.service import create_workspace


@pytest.mark.parametrize('action', ['accept', 'decline'])
@pytest.mark.parametrize('revoked', [False, True])
def test_conclusion_pipeline(settings, action, revoked):
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    settings.redis_url = 'redis://127.0.0.1:26379'
    settings.redis_key_prefix = 'test:conclusion:' + uuid4().hex + ':'
    migrate(settings)
    app = create_app(settings)
    delivery = OutboxDelivery(settings)
    try:
        with TestClient(app) as client, ExitStack() as stack:
            identities = []
            with app.state.database.transaction() as s:
                for label in ['owner', 'recipient', 'stranger']:
                    uid = str(uuid4())
                    email = label + '@example.com'
                    s.execute(users.insert().values(id=uid, email=email, name=label,
                        created_at='2026-01-01', updated_at='2026-01-01'))
                    workspace = create_workspace(s, uid, label, label)
                    identities.append((uid, email, workspace,
                        issue_session(uid, email, label, settings.auth_secret, 60)))
            owner, recipient, stranger = identities
            def connect(identity, workspace=None):
                ws = stack.enter_context(client.websocket_connect('/ws?workspace_id=' +
                    (workspace or identity[2]['id'])))
                ws.send_json({'type': 'auth', 'payload': {'token': identity[3]}})
                assert json.loads(receive(ws)['text']) == {'type': 'auth_ack'}
                return ws
            sockets = [connect(i) for i in identities]
            def post(identity, path, **kwargs):
                return client.post(path, headers={'Authorization': 'Bearer ' + identity[3]}, **kwargs)
            def events():
                with app.state.database.transaction() as s:
                    return [json.loads(raw) for raw in s.scalars(select(outbox.c.envelope))]
            response = post(owner, '/api/workspaces/' + owner[2]['id'] + '/members',
                json={'email': recipient[1]})
            assert response.status_code == 201, response.text
            invitation = response.json()
            created = events()
            assert len(created) == 1
            assert created[0]['type'] == 'invitation:created'
            assert delivery.dispatch(app.state.database) == 1
            handled(app, created[0], delivery.client.xrevrange(delivery.channel, count=1)[0][0])
            assert json.loads(receive(sockets[1])['text']) == dict(type='invitation:created',
                payload={'invitation': invitation, 'workspace_name': 'owner'},
                actor_id=owner[0], actor_type='member')
            for ws in sockets:
                pong(ws)
            path = '/api/invitations/' + invitation['id'] + '/' + action
            denied = post(stranger, path)
            assert denied.status_code == 403, denied.text
            assert events() == created
            response = post(recipient, path)
            assert response.status_code == (200 if action == 'accept' else 204), response.text
            if action == 'accept':
                member = response.json()
                expected = [('member:added', {'member': member, 'workspace_name': 'owner'}),
                    ('invitation:accepted', {'invitation_id': invitation['id'], 'member': member})]
                sockets.append(connect(recipient, owner[2]['id']))
            else:
                expected = [('invitation:declined', {'invitation_id': invitation['id'],
                    'invitee_email': recipient[1]})]
            conclusions = [e for e in events() if e['eventID'] != created[0]['eventID']]
            assert [(e['type'], e['payload']) for e in conclusions] == expected
            for event in conclusions:
                assert event['workspaceID'] == owner[2]['id']
                assert event['actorID'] == recipient[0]
                assert event['actorType'] == 'member'
            if revoked:
                with app.state.database.transaction() as s:
                    revoke_session(s, settings, recipient[3])
            for _ in expected:
                assert delivery.dispatch(app.state.database) == 1
            handled(app, conclusions[-1], delivery.client.xrevrange(delivery.channel, count=1)[0][0])
            for index, ws in enumerate(sockets):
                if revoked and index in [1, 3]:
                    assert receive(ws) == {'type': 'websocket.close', 'code': 1008, 'reason': ''}
                    continue
                if index != 2:
                    for kind, payload in expected:
                        assert json.loads(receive(ws)['text']) == dict(type=kind, payload=payload,
                            actor_id=recipient[0], actor_type='member')
                pong(ws)
            for event in conclusions:
                duplicate = delivery.client.xadd(delivery.channel, {'envelope': json.dumps(event)})
                handled(app, event, duplicate)
                for index, ws in enumerate(sockets):
                    if not (revoked and index in [1, 3]):
                        pong(ws)
    finally:
        delivery.client.delete(delivery.channel)
        delivery.close()
