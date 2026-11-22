import asyncio,json
import pytest
from workpal_backend.realtime.hub import Connection,Hub
from workpal_backend.realtime.protocol import project_event,resolve_audience

class Socket:
    def __init__(self):self.frames=[];self.closed=False
    async def send_text(self,raw):self.frames.append(json.loads(raw))
    async def close(self,code):self.closed=True

@pytest.mark.parametrize('kind,hints',[
 ('chat:message',{'chatSessionOwnerID':'creator'}),
 ('chat:future',{'chatSessionOwnerID':'creator'}),
 ('task:message',{'chatSessionID':'chat','chatSessionOwnerID':'creator'}),
 ('pin:created',{'memberPrivateUserID':'creator'}),
 ('custom:private',{'memberPrivateUserID':'creator'}),
])
def test_private_frames_only_reach_workspace_bound_recipient(kind,hints):
    async def run():
        h=Hub();sockets=[]
        for workspace,user in [('w','creator'),('w','peer'),('other','creator')]:
            ws=Socket();sockets.append(ws);h.connections.add(Connection(ws,lambda:None,workspace,user))
        event=dict(type=kind,workspaceID='w',payload={'text':'private'},**hints)
        await h.publish(event)
        assert sockets[0].frames==[dict(type=kind,payload={'text':'private'},actor_id='',actor_type='')]
        assert sockets[1].frames==sockets[2].frames==[]
    asyncio.run(run())


def test_missing_recipient_drops_and_chat_recipient_takes_precedence():
    for kind in ['chat:done','pin:created','issue_view_preference:changed']:
        assert resolve_audience(dict(type=kind,workspaceID='w',payload={})) is None
    assert resolve_audience(dict(type='chat:done',workspaceID='w',payload={},chatSessionOwnerID='a',memberPrivateUserID='b'))==('workspace_member','w:a')


def test_revalidation_revocation_and_unsubscribe_private_room():
    async def run():
        h=Hub();ws=Socket();valid=[True]
        def check():
            if not valid[0]:raise ValueError('revoked')
        c=Connection(ws,check,'w','u');h.connections.add(c)
        e=dict(type='chat:message',workspaceID='w',chatSessionOwnerID='u',payload='content')
        c.rooms.discard(('workspace_member','w:u'));await h.publish(e)
        assert not ws.frames
        c.rooms.add(('workspace_member','w:u'));valid[0]=False;await h.publish(e)
        assert not ws.frames and ws.closed
    asyncio.run(run())


def test_private_projection_removes_internal_error_without_mutating_producer():
    e=dict(type='task:failed',workspaceID='w',memberPrivateUserID='u',payload={'error':'secret','task_id':'t'})
    assert project_event(e,'w')['payload']=={'task_id':'t'}
    assert e['payload']['error']=='secret'


def test_outbox_redis_private_frame_reaches_only_bound_creator(settings, isolated_relay_redis_port):
    import anyio
    from uuid import uuid4
    from fastapi.testclient import TestClient
    from sqlalchemy import text
    from workpal_backend.app import create_app
    from workpal_backend.infrastructure.database import migrate
    from workpal_backend.infrastructure.delivery import OutboxDelivery
    from workpal_backend.infrastructure.outbox import append_event
    from workpal_backend.auth.tokens import issue_session
    from workpal_backend.workspaces.service import create_workspace
    settings.redis_url=f'redis://127.0.0.1:{isolated_relay_redis_port}'
    settings.redis_key_prefix='test:private-bridge:'+uuid4().hex+':'
    migrate(settings);app=create_app(settings);delivery=OutboxDelivery(settings)
    creator,peer=str(uuid4()),str(uuid4())
    try:
        with TestClient(app) as client:
            with app.state.database.transaction() as session:
                for user in [creator,peer]:
                    session.execute(text("INSERT INTO users(id,email,name,created_at,updated_at) VALUES (:u,:email,'Fixture','2026-01-01','2026-01-01')"),dict(u=user,email=user+'@example.com'))
                workspace=create_workspace(session,creator,'Private bridge','private-bridge')
                other=create_workspace(session,creator,'Other bridge','other-bridge')
                session.execute(text("INSERT INTO members(id,workspace_id,user_id,role,created_at) VALUES (:id,:w,:u,'member','2026-01-01')"),dict(id=str(uuid4()),w=workspace['id'],u=peer))
            def connect(user,w):
                token=issue_session(user,user+'@example.com','Fixture',settings.auth_secret,60)
                return client.websocket_connect('/ws?workspace_id='+w,headers={'cookie':'workpal_auth='+token})
            def receive_raw(ws):
                async def bounded():
                    with anyio.fail_after(2):return await ws._send_rx.receive()
                return ws.portal.call(bounded)
            def receive(ws):return json.loads(receive_raw(ws)['text'])
            with connect(creator,workspace['id']) as owner,connect(peer,workspace['id']) as teammate,connect(creator,other['id']) as foreign:
                for ws in [owner,teammate,foreign]:ws.send_json({'type':'ping'});assert receive(ws)=={'type':'pong'}
                event=dict(type='chat:message',workspaceID=workspace['id'],chatSessionOwnerID=creator,payload={'text':'fixture private bytes'})
                with app.state.database.transaction() as session:append_event(session,event)
                assert delivery.dispatch(app.state.database)==1
                assert receive(owner)==dict(type='chat:message',payload=event['payload'],actor_id='',actor_type='')
                for ws in [teammate,foreign]:ws.send_json({'type':'ping'});assert receive(ws)=={'type':'pong'}
                with app.state.database.transaction() as session:
                    session.execute(text('DELETE FROM members WHERE workspace_id=:w AND user_id=:u'),dict(w=workspace['id'],u=creator))
                    append_event(session,event)
                assert delivery.dispatch(app.state.database)==1
                assert receive_raw(owner)['type']=='websocket.close'
                foreign.send_json({'type':'ping'});assert receive(foreign)=={'type':'pong'}
            assert not app.state.realtime.connections
    finally:
        delivery.client.delete(delivery.channel);delivery.close()
