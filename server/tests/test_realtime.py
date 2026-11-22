import json
"""Connection unit integration, not mutation-to-browser acceptance."""
import asyncio
import pytest
from workpal_backend.realtime.hub import Connection, Hub
from workpal_backend.realtime.protocol import ProjectionError

class Socket:
    def __init__(self): self.frames = []; self.closed = False
    async def send_text(self, raw): self.frames.append(json.loads(raw))
    async def close(self, code): self.closed = True

def test_write_revalidates_and_drops_revoked_content():
    async def exercise():
        socket = Socket()
        valid = True
        def check():
            if not valid: raise ValueError('revoked')
        connection = Connection(socket, check, 'w', 'u')
        await connection.send({'type': 'pong'})
        valid = False
        await connection.send({'type': 'private'})
        assert socket.frames == [{'type': 'pong'}]
        assert socket.closed
    asyncio.run(exercise())

def test_unknown_projection_is_observable():
    async def exercise():
        with pytest.raises(ProjectionError):
            await Hub().publish({'type': 'unknown', 'workspaceID': 'w'})
    asyncio.run(exercise())

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from starlette.testclient import WebSocketDenialResponse
from workpal_backend.app import create_app
from workpal_backend.infrastructure.database import migrate

@pytest.fixture
def live(settings):
    settings.dev_auth = True
    settings.auth_secret = 's' * 32
    migrate(settings)
    app = create_app(settings)
    with TestClient(app) as client:
        login = client.post('/auth/verify-code', json={'email':'dev@workpal.local','code':'888888'}).json()
        workspace = client.post('/api/workspaces', headers={'Authorization':'Bearer '+login['token']}, json={'name':'Realtime','slug':'realtime','issue_prefix':'RT'}).json()
        yield client, app, login, workspace

def test_real_cookie_ping_and_subscription(live):
    client, app, login, workspace = live
    with client.websocket_connect('/ws?workspace_slug=realtime') as ws:
        ws.send_json({'type':'ping'})
        assert ws.receive_json() == {'type':'pong'}
        for scope, room, error in [('workspace','foreign','forbidden'), ('chat','x','forbidden'), ('unknown','x','unknown_scope'), ('','','invalid payload')]:
            ws.send_json({'type':'subscribe','payload':{'scope':scope,'id':room}})
            assert ws.receive_json() == {'type':'subscribe_error','payload':{'scope':scope,'id':room,'error':error}}

@pytest.mark.parametrize('origin', ['http://evil.example','https://testserver.evil'])
def test_real_origin_rejection(live, origin):
    client, app, login, workspace = live
    with pytest.raises(WebSocketDenialResponse) as denied:
        with client.websocket_connect('/ws?workspace_slug=realtime', headers={'origin':origin,'x-forwarded-host':'evil.example','x-forwarded-proto':'https'}):
            pytest.fail('origin accepted')
    assert denied.value.status_code == 403
    assert denied.value.text == 'Forbidden\n'
    assert denied.value.headers['sec-websocket-version'] == '13'

def test_real_first_auth_and_query_token_rejection(live):
    client, app, login, workspace = live
    client.cookies.clear()
    with client.websocket_connect('/ws?workspace_slug=realtime&token='+login['token']) as ws:
        ws.send_json({'type':'ping'})
        assert 'error' in ws.receive_json()
        assert ws.receive()['code'] == 1008
    with client.websocket_connect('/ws?workspace_slug=realtime') as ws:
        ws.send_json({'type':'auth','payload':{'token':login['token']}})
        assert ws.receive_json() == {'type':'auth_ack'}
        ws.send_text('x' * 65537)
        assert ws.receive()['code'] == 1009

def test_real_logout_keeps_established_socket(live):
    client, app, login, workspace = live
    with client.websocket_connect('/ws?workspace_slug=realtime') as ws:
        assert client.post('/auth/logout').status_code == 200
        ws.send_json({'type':'ping'})
        assert ws.receive_json() == {'type':'pong'}

@pytest.mark.parametrize('frame', [[], None, {'type':'auth','payload':[]}, {'type':'auth','payload':{'token':'bad'}}])
def test_real_malformed_auth(live, frame):
    client, app, login, workspace = live
    client.cookies.clear()
    with client.websocket_connect('/ws?workspace_slug=realtime') as ws:
        ws.send_json(frame)
        assert 'error' in ws.receive_json()
        assert ws.receive()['code'] == 1008


def test_peer_disconnect_during_close_is_idempotent():
    class DisconnectedSocket:
        async def close(self, code):
            raise WebSocketDisconnect(code=1006)
    async def exercise():
        connection = Connection(DisconnectedSocket(), lambda: None, 'w', 'u')
        await connection.close()
        await connection.close()
        assert connection.closed
    asyncio.run(exercise())


def test_nonmember_cannot_open_workspace_socket(live):
    client, app, login, workspace = live
    from uuid import uuid4
    from workpal_backend.auth.models import users
    from workpal_backend.workspaces import service
    with app.state.database.transaction() as session:
        outsider = str(uuid4())
        session.execute(users.insert().values(id=outsider, email='socket-private@example.com', name='Private', created_at='2026-01-01T00:00:00Z', updated_at='2026-01-01T00:00:00Z'))
        service.create_workspace(session, outsider, 'Private', 'socket-private')
    with pytest.raises(WebSocketDenialResponse) as denied:
        with client.websocket_connect('/ws?workspace_slug=socket-private'):
            pytest.fail('nonmember subscribed')
    assert denied.value.status_code in (403, 404)


def test_subscription_denial_metrics_exclude_malformed_payload(live):
    client, app, login, workspace = live
    with client.websocket_connect('/ws?workspace_slug=realtime') as ws:
        for scope, room in [('workspace','foreign'),('unknown','x'),('','')]:
            ws.send_json({'type':'subscribe','payload':{'scope':scope,'id':room}})
            assert ws.receive_json()['type'] == 'subscribe_error'
        assert app.state.realtime.metrics.snapshot()['subscribe_denied_total'] == {'workspace':1,'unknown':1}


@pytest.mark.parametrize('pre_auth', [False,True])
def test_oversize_counter_before_and_after_authentication(live, pre_auth):
    client, app, login, workspace = live
    if pre_auth:
        client.cookies.clear()
    with client.websocket_connect('/ws?workspace_slug=realtime') as ws:
        ws.send_text('x' * 65537)
        assert ws.receive()['code'] == 1009
        assert app.state.realtime.metrics.snapshot()['inbound_too_large_total'] == 1


@pytest.mark.parametrize('server_limit', [False,True])
def test_disconnect_size_metric_requires_server_limit_marker(live,server_limit):
    client,app,login,workspace=live
    with client.websocket_connect('/ws?workspace_slug=realtime') as ws:
        message={'type':'websocket.disconnect','code':1009}
        if server_limit:message['workpal.too_large']=True
        ws.send(message)
        async def disconnected():
            async with asyncio.timeout(1):
                while app.state.realtime.connections:
                    await asyncio.sleep(.001)
        ws.portal.call(disconnected)
    assert app.state.realtime.metrics.inbound_too_large_total==int(server_limit)


def test_first_auth_uses_go_case_folding_and_nested_struct_merging(live):
    client,app,login,workspace=live
    import json
    client.cookies.clear()
    with client.websocket_connect('/ws?workspace_slug=realtime') as ws:
        ws.send_text('{"TYPE":"auth","PAYLOAD":{"TOKEN":'+json.dumps(login['token'])+'},"payload":null}')
        assert ws.receive_json()=={'type':'auth_ack'}
        ws.send_json({'type':'ping'})
        assert ws.receive_json()=={'type':'pong'}


def test_auth_ack_precedes_content_membership_revalidation(live):
    client,app,login,workspace=live
    calls=[]
    async def denied(identity):
        calls.append(identity)
        return False
    app.state.realtime.membership_batcher.authorize=denied
    client.cookies.clear()
    with client.websocket_connect('/ws?workspace_slug=realtime') as ws:
        ws.send_json({'type':'auth','payload':{'token':login['token']}})
        assert ws.receive_json()=={'type':'auth_ack'}
        assert calls==[]
        ws.send_json({'type':'ping'})
        assert ws.receive()['code']==1008
        assert len(calls)==1


def test_failed_auth_ack_closes_without_attempting_an_error_frame(live,monkeypatch):
    from starlette.websockets import WebSocket
    calls=[]
    async def failed_text(self,text):
        calls.append(('text',text))
        raise OSError('write failed')
    async def unexpected_error(self,value,*args,**kwargs):calls.append(('error',value))
    monkeypatch.setattr(WebSocket,'send_text',failed_text)
    monkeypatch.setattr(WebSocket,'send_json',unexpected_error)
    client,app,login,workspace=live
    client.cookies.clear()
    with client.websocket_connect('/ws?workspace_slug=realtime') as ws:
        ws.send_json({'type':'auth','payload':{'token':login['token']}})
        assert ws.receive()['code']==1008
    assert calls==[('text','{"type":"auth_ack"}')]
    assert app.state.realtime.metrics.connects_total==0
