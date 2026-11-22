import asyncio
from workpal_backend.realtime.hub import Hub,Connection


class Socket:
    async def close(self,code):pass
    async def send_text(self,value):pass


def connection(workspace='w',user='u'):
    return Connection(Socket(),lambda:None,workspace,user)


def test_first_last_callbacks_follow_shared_rooms_and_duplicate_operations():
    h=Hub();calls=[]
    h.set_subscription_callbacks(lambda s,i:calls.append(('first',s,i)),lambda s,i:calls.append(('last',s,i)))
    a,b=connection(),connection(user='v')
    h.register(a);h.register(b)
    assert calls==[('first','workspace','w'),('first','user','u'),('first','workspace_member','w:u'),('first','user','v'),('first','workspace_member','w:v')]
    assert h.local_scopes()=={('workspace','w'),('user','u'),('user','v'),('workspace_member','w:u'),('workspace_member','w:v')}
    assert not h.subscribe(a,'workspace','w')
    assert h.subscribe(a,'chat','c')
    assert h.subscribe(b,'chat','c')
    assert h.unsubscribe(a,'chat','c')
    assert not h.unsubscribe(a,'chat','c')
    assert h.has_local_subscribers('chat','c')
    assert h.unsubscribe(b,'chat','c')
    assert calls[-2:]==[('first','chat','c'),('last','chat','c')]
    assert not h.has_local_subscribers('chat','c')
    h.unregister(a)
    assert h.has_local_subscribers('workspace','w')
    assert not a.rooms and a not in h.connections
    h.unregister(a)
    h.unregister(b)
    assert h.local_scopes()==set()
    assert calls.count(('last','workspace','w'))==1


def test_unregistered_empty_and_stopped_connections_cannot_create_rooms():
    h=Hub();c=connection()
    assert not h.subscribe(c,'chat','c') and not h.unsubscribe(c,'workspace','w')
    c.closed=True;h.register(c)
    assert h.local_scopes()==set()
    empty=connection('','u');h.register(empty)
    assert h.local_scopes()=={('user','u')}
    assert not h.subscribe(empty,'','c') and not h.subscribe(empty,'chat','')
    h.unregister(empty)
    assert h.local_scopes()==set()


def test_callback_replacement_is_not_retroactive_and_close_removes_last_subscriber():
    async def run():
        h=Hub();c=connection();h.register(c);events=[]
        h.set_subscription_callbacks(lambda *room:events.append(('first',room)),lambda *room:events.append(('last',room)))
        assert events==[]
        await c.close()
        assert set(events)=={('last',('workspace','w')),('last',('user','u')),('last',('workspace_member','w:u'))}
        assert not h.connections
        h.set_subscription_callbacks(None,None)
        c=connection();h.register(c);await h.close()
        assert not h.connections and len(events)==3
    asyncio.run(run())

from test_realtime import live


def test_real_websocket_register_subscribe_unsubscribe_and_disconnect_callbacks(live):
    client,app,login,workspace=live
    h=app.state.realtime;events=[]
    h.set_subscription_callbacks(lambda s,i:events.append(('first',s,i)),lambda s,i:events.append(('last',s,i)))
    with client.websocket_connect('/ws?workspace_slug=realtime') as ws:
        ws.send_json({'type':'ping'})
        assert ws.receive_json()=={'type':'pong'}
        initial=h.local_scopes()
        assert {scope for scope,_ in initial}=={'workspace','user','workspace_member'}
        room=next(room for scope,room in initial if scope=='workspace')
        ws.send_json({'type':'unsubscribe','payload':{'scope':'workspace','id':room}})
        assert ws.receive_json()['type']=='unsubscribe_ack'
        assert not h.has_local_subscribers('workspace',room)
        ws.send_json({'type':'subscribe','payload':{'scope':'workspace','id':room}})
        assert ws.receive_json()['type']=='subscribe_ack'
        assert h.has_local_subscribers('workspace',room)
    assert h.local_scopes()==set()
    assert events.count(('first','workspace',room))==2
    assert events.count(('last','workspace',room))==2
