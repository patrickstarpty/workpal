import asyncio,json
from workpal_backend.realtime.hub import Hub,Connection
from workpal_backend.realtime.relay_envelope import Envelope


class Socket:
    def __init__(self):self.frames=[]
    async def send_text(self,raw):self.frames.append(json.loads(raw))
    async def close(self,code):pass


def test_envelope_routes_to_real_hub_with_event_id_and_user_exclusion():
    from workpal_backend.realtime.relay_delivery import deliver_envelope
    async def run():
        h=Hub();clients=[];sockets=[]
        for workspace,user in [('w','u'),('w','v'),('x','u')]:
            socket=Socket();c=Connection(socket,lambda:None,workspace,user);h.register(c);clients.append(c);sockets.append(socket)
        try:
            deliver_envelope(h,Envelope(scope='workspace',scope_id='w',event_id='e',payload_json=b'{"type":"x"}'))
            deliver_envelope(h,Envelope(scope='workspace',scope_id='w',event_id='e',payload_json=b'{"type":"duplicate"}'))
            deliver_envelope(h,Envelope(scope='user',scope_id='u',workspace_id='w',event_id='f',payload_json=b'{"type":"personal"}'))
            deliver_envelope(h,Envelope(scope='global',event_id='g',payload_json=b'{"type":"all"}'))
            await asyncio.gather(*(c._writer.flush() for c in clients))
            assert sockets[0].frames==sockets[1].frames==[{'type':'x','event_id':'e'},{'type':'all','event_id':'g'}]
            assert sockets[2].frames==[{'type':'personal','event_id':'f'},{'type':'all','event_id':'g'}]
        finally:await h.close()
    asyncio.run(run())


def test_optional_external_deliverers_never_fall_back_to_public_hub():
    from workpal_backend.realtime.relay_delivery import deliver_envelope
    h=Hub();calls=[]
    for scope in ['daemon_runtime','wecom_outbound']:
        env=Envelope(scope=scope,scope_id='id',event_id='e',payload_json=b'{"x":1}')
        deliver_envelope(h,env)
        deliver_envelope(h,env,daemon_runtime=lambda *args:calls.append(('daemon',args)),wecom_outbound=lambda *args:calls.append(('wecom',args)))
    assert calls==[('daemon',('id',b'{"event_id":"e","x":1}','e')),('wecom',('id',b'{"event_id":"e","x":1}','e'))]
    deliver_envelope(h,Envelope(scope='daemon_runtime',payload_json=b''),daemon_runtime=lambda *args:calls.append(args))
    assert len(calls)==2
