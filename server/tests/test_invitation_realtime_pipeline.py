"""Invitation HTTP/outbox/Redis/consumer integration, with bounded socket reads."""
import json
import time
from contextlib import ExitStack
from uuid import uuid4

import pytest
from sqlalchemy import select, delete
from fastapi.testclient import TestClient

from test_realtime_audience import receive, pong
from workpal_backend.app import create_app
from workpal_backend.auth.models import users
from workpal_backend.auth.sessions import revoke_session
from workpal_backend.auth.tokens import issue_session
from workpal_backend.infrastructure.database import migrate
from workpal_backend.infrastructure.delivery import OutboxDelivery
from workpal_backend.infrastructure.outbox import outbox
from workpal_backend.realtime.consumer import checkpoints, receipts
from workpal_backend.workspaces.models import members
from workpal_backend.workspaces.service import create_workspace


def handled(app, event, stream_id):
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        with app.state.database.transaction() as s:
            receipt = s.execute(select(receipts).where(receipts.c.event_id == event['eventID'])).first()
            position = s.execute(select(checkpoints.c.stream_id)).scalar_one_or_none()
        if receipt and position == stream_id.decode():
            return
        time.sleep(.01)
    pytest.fail('Running consumer did not persist receipt/checkpoint')


@pytest.mark.parametrize('mode', ['normal', 'null', 'revoke_session', 'remove_membership'])
def test_invitation_pipeline(settings, mode, isolated_relay_redis_port):
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    settings.redis_url = f'redis://127.0.0.1:{isolated_relay_redis_port}'
    settings.redis_key_prefix = 'test:invitation-pipeline:' + uuid4().hex + ':'
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
                    token = issue_session(uid, email, label, settings.auth_secret, 60)
                    identities.append((uid, email, workspace, token))
            sockets = []
            for identity in identities:
                ws = stack.enter_context(client.websocket_connect('/ws?workspace_id=' + identity[2]['id']))
                ws.send_json({'type': 'auth', 'payload': {'token': identity[3]}})
                assert json.loads(receive(ws)['text']) == {'type': 'auth_ack'}
                sockets.append(ws)
            owner, recipient, stranger = identities
            headers = {'Authorization': 'Bearer ' + owner[3]}
            source = owner[2]['id']
            email = 'unknown@example.com' if mode == 'null' else recipient[1]
            response = client.post('/api/workspaces/' + source + '/members', headers=headers, json={'email': email})
            assert response.status_code == 201, response.text
            invitation = response.json()
            if mode in ['revoke_session', 'remove_membership']:
                with app.state.database.transaction() as s:
                    if mode == 'revoke_session':
                        revoke_session(s, settings, recipient[3])
                    else:
                        s.execute(delete(members).where(members.c.user_id == recipient[0]))
            for kind in ['invitation:created', 'invitation:revoked']:
                if kind.endswith('revoked'):
                    response = client.delete('/api/workspaces/' + source + '/invitations/' + invitation['id'], headers=headers)
                    assert response.status_code == 204, response.text
                with app.state.database.transaction() as s:
                    events = [json.loads(raw) for raw in s.scalars(select(outbox.c.envelope))]
                event = next(e for e in events if e['type'] == kind)
                assert event['workspaceID'] == source
                assert event['actorID'] == owner[0]
                assert event['actorType'] == 'member'
                expected = ({'invitation': invitation, 'workspace_name': 'owner'} if kind.endswith('created') else
                    {'invitation_id': invitation['id'], 'invitee_email': email,
                     'invitee_user_id': None if mode == 'null' else recipient[0]})
                assert event['payload'] == expected
                assert delivery.dispatch(app.state.database) == 1
                stream_id = delivery.client.xrevrange(delivery.channel, count=1)[0][0]
                handled(app, event, stream_id)
                if mode in ['normal', 'revoke_session']:
                    assert json.loads(receive(sockets[1])['text']) == dict(type=kind, payload=expected,
                        actor_id=owner[0], actor_type='member')
                elif mode == 'null':
                    pong(sockets[1])
                elif kind.endswith('created'):
                    assert receive(sockets[1]) == {'type': 'websocket.close', 'code': 1008, 'reason': ''}
                pong(sockets[0])
                pong(sockets[2])
                duplicate = delivery.client.xadd(delivery.channel, {'envelope': json.dumps(event)})
                handled(app, event, duplicate)
                for index in ([0, 1, 2] if mode in ['normal', 'null', 'revoke_session'] else [0, 2]):
                    pong(sockets[index])
    finally:
        delivery.client.delete(delivery.channel)
        delivery.close()
