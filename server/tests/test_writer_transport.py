"""Actual loopback uvicorn/wsproto transport, not TestClient ASGI messages."""
import socket
import threading
import time
from fastapi import FastAPI,WebSocket
import uvicorn
from wsproto import WSConnection,ConnectionType,events
from workpal_backend.realtime.hub import Hub,Connection


def test_graceful_connection_drains_text_then_sends_empty_close_frame():
    app=FastAPI();checks=[]
    @app.websocket('/')
    async def endpoint(ws:WebSocket):
        await ws.accept()
        h=Hub();c=Connection(ws,lambda:checks.append(True),'w','u');h.register(c)
        for index in range(65):assert c.enqueue({'n':index})
        h.unregister(c)
        c.finish()
        assert not c.enqueue({'n':'late'})
        await c._writer.flush()
    listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen()
    server=uvicorn.Server(uvicorn.Config(app,ws='workpal_backend.realtime.transport:RelayWebSocketProtocol',lifespan='off',log_level='error',ws_ping_interval=None))
    thread=threading.Thread(target=server.run,kwargs={'sockets':[listener]},daemon=True)
    thread.start()
    try:
        deadline=time.monotonic()+3
        while not server.started:
            assert thread.is_alive() and time.monotonic()<deadline
            time.sleep(.005)
        with socket.create_connection(listener.getsockname(),timeout=3) as peer:
            protocol=WSConnection(ConnectionType.CLIENT)
            peer.sendall(protocol.send(events.Request(host='localhost',target='/')))
            raw=b'';frames=[];closed=False
            while not closed:
                data=peer.recv(65536);assert data
                raw+=data;protocol.receive_data(data)
                for event in protocol.events():
                    if isinstance(event,events.TextMessage):frames.append(event.data)
                    if isinstance(event,events.CloseConnection):
                        assert event.code==1005
                        peer.sendall(protocol.send(event.response()))
                        closed=True
            assert frames==['{"n":'+str(i)+'}' for i in range(65)]
            assert raw.endswith(b'\x88\x00')
            assert len(checks)==3
    finally:
        server.should_exit=True
        thread.join(5);listener.close()
        assert not thread.is_alive()

from contextlib import contextmanager
import pytest

@contextmanager
def serve_relay(app):
    from workpal_backend.realtime.transport import RelayWebSocketProtocol
    listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen()
    server=uvicorn.Server(uvicorn.Config(app,ws=RelayWebSocketProtocol,lifespan='off',log_level='error',ws_ping_interval=None))
    thread=threading.Thread(target=server.run,kwargs={'sockets':[listener]},daemon=True);thread.start()
    try:
        deadline=time.monotonic()+3
        while not server.started:
            assert thread.is_alive() and time.monotonic()<deadline
            time.sleep(.005)
        yield listener.getsockname()
    finally:
        server.should_exit=True;thread.join(5);listener.close()
        assert not thread.is_alive()


@pytest.mark.parametrize('deny_on,expected_count',[(1,0),(2,32)])
def test_membership_denial_closes_tcp_without_close_frame(deny_on,expected_count):
    app=FastAPI();lookups=[]
    @app.websocket('/')
    async def endpoint(ws:WebSocket):
        await ws.accept()
        def check():
            lookups.append(True)
            if len(lookups)>=deny_on:raise PermissionError('revoked')
        c=Connection(ws,check,'w','u')
        for index in range(65):c.enqueue({'n':index})
        await c._writer.flush()
    with serve_relay(app) as address, socket.create_connection(address,timeout=3) as peer:
        protocol=WSConnection(ConnectionType.CLIENT)
        peer.sendall(protocol.send(events.Request(host='localhost',target='/')))
        frames=[];wire_closes=[];raw=b''
        while True:
            data=peer.recv(65536)
            if not data:break
            raw+=data;protocol.receive_data(data)
            for event in protocol.events():
                if isinstance(event,events.TextMessage):frames.append(event.data)
                if isinstance(event,events.CloseConnection):wire_closes.append(event.code)
        assert wire_closes==[]
        assert frames==['{"n":'+str(i)+'}' for i in range(expected_count)]
        if not expected_count:assert raw.split(b'\r\n\r\n',1)[1]==b''
        protocol.receive_data(None)
        assert [e.code for e in protocol.events() if isinstance(e,events.CloseConnection)]==[1006]


def test_abort_bypasses_transport_backpressure():
    import asyncio
    from workpal_backend.realtime.transport import RelayWebSocketProtocol
    async def run():
        class Transport:
            closed=False
            def close(self):self.closed=True
        protocol=RelayWebSocketProtocol.__new__(RelayWebSocketProtocol)
        protocol.transport=Transport();protocol.writable=asyncio.Event()
        protocol.handshake_complete=True;protocol.close_sent=False;protocol.disconnected=False
        protocol.queue=asyncio.Queue();protocol.stop_keepalive=lambda:None
        await asyncio.wait_for(protocol.send({'type':'websocket.close','workpal.abort':True}),.1)
        assert protocol.transport.closed and protocol.writable.is_set()
        assert (await protocol.queue.get())['code']==1006
    asyncio.run(run())


def test_explicit_policy_close_still_sends_requested_control_frame():
    app=FastAPI()
    @app.websocket('/')
    async def endpoint(ws:WebSocket):
        await ws.accept();await ws.close(code=1008)
    with serve_relay(app) as address, socket.create_connection(address,timeout=3) as peer:
        protocol=WSConnection(ConnectionType.CLIENT)
        peer.sendall(protocol.send(events.Request(host='localhost',target='/')))
        closed=False;raw=b''
        while not closed:
            data=peer.recv(65536);assert data;raw+=data;protocol.receive_data(data)
            for event in protocol.events():
                if isinstance(event,events.CloseConnection):
                    assert event.code==1008
                    peer.sendall(protocol.send(event.response()));closed=True
        assert raw.endswith(b'\x88\x02\x03\xf0')


@pytest.mark.parametrize('state,expected_frames,expected_close',[
    ('removed',['notice'],1006),('error',[],1006),('busy',[],1006),('rejoined',['still-here'],1005),
])
def test_hub_removal_notice_and_tcp_close_on_real_socket(state,expected_frames,expected_close):
    import asyncio
    raw=b'{"type":"member:removed","payload":{"user_id":"u","workspace_id":"w"}}'
    app=FastAPI()
    @app.websocket('/')
    async def endpoint(ws:WebSocket):
        await ws.accept()
        async def check(w,u):
            if state=='error':raise OSError('lookup unavailable')
            return state=='rejoined'
        h=Hub(membership_check=check);c=Connection(ws,lambda:None,'w','u');h.register(c)
        if state=='busy':
            await c.lock.acquire();c.try_send(b'must-not-leak')
        try:
            h.broadcast_to_scope('workspace','w',raw,'event')
            await h.removals.join()
            if state=='rejoined':
                c.try_send(b'still-here');c.finish();await c._writer.flush()
        finally:
            if state=='busy':c.lock.release()
            await h.close()
    with serve_relay(app) as address, socket.create_connection(address,timeout=3) as peer:
        protocol=WSConnection(ConnectionType.CLIENT)
        peer.sendall(protocol.send(events.Request(host='localhost',target='/')))
        frames=[];close_code=None
        while close_code is None:
            data=peer.recv(65536);protocol.receive_data(data if data else None)
            for event in protocol.events():
                if isinstance(event,events.TextMessage):frames.append(event.data)
                if isinstance(event,events.CloseConnection):
                    close_code=event.code
                    if data:peer.sendall(protocol.send(event.response()))
        assert frames==[raw.decode() if frame=='notice' else frame for frame in expected_frames]
        assert close_code==expected_close


@pytest.mark.parametrize('payload',[b'opaque\xff', b'\xed\xa0\x80', b'\xc0\xaf', b'\x00\xfe'])
def test_canonical_transport_preserves_opaque_text_frame_bytes(payload):
    app=FastAPI()
    @app.websocket('/')
    async def endpoint(ws:WebSocket):
        await ws.accept()
        connection=Connection(ws,lambda:None,'w','u')
        connection.try_send(payload)
        connection.finish()
        await connection._writer.flush()
    with serve_relay(app) as address, socket.create_connection(address,timeout=3) as peer:
        peer.sendall(b'GET / HTTP/1.1\r\nHost: localhost\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\nSec-WebSocket-Version: 13\r\n\r\n')
        received=b''
        while b'\r\n\r\n' not in received:
            chunk=peer.recv(65536);assert chunk;received+=chunk
        header,wire=received.split(b'\r\n\r\n',1)
        assert header.startswith(b'HTTP/1.1 101')
        expected=b'\x81'+bytes([len(payload)])+payload+b'\x88\x00'
        while len(wire)<len(expected):
            chunk=peer.recv(65536)
            if not chunk:break
            wire+=chunk
        assert wire==expected


@pytest.mark.parametrize('fragmented',[False,True])
def test_canonical_transport_passes_opaque_inbound_text_bytes_to_application(fragmented):
    payload=b'{"type":"fixture","value":"\xff"}'
    app=FastAPI()
    @app.websocket('/')
    async def endpoint(ws:WebSocket):
        await ws.accept()
        message=await ws.receive()
        if message['type']=='websocket.receive':
            raw=message.get('bytes')
            if raw is None:raw=message['text'].encode()
            await ws.send_text(raw.hex())
            await ws.close()
    def masked(opcode,data,final):
        mask=b'abcd'
        return bytes([opcode|(0x80 if final else 0),0x80|len(data)])+mask+bytes(b^mask[i%4] for i,b in enumerate(data))
    with serve_relay(app) as address, socket.create_connection(address,timeout=3) as peer:
        protocol=WSConnection(ConnectionType.CLIENT)
        peer.sendall(protocol.send(events.Request(host='localhost',target='/')))
        accepted=False;frames=[];close=None
        while not accepted:
            protocol.receive_data(peer.recv(65536))
            accepted=any(isinstance(event,events.AcceptConnection) for event in protocol.events())
        if fragmented:
            peer.sendall(masked(1,payload[:12],False)+masked(0,payload[12:],True))
        else:
            peer.sendall(masked(1,payload,True))
        while close is None:
            data=peer.recv(65536);protocol.receive_data(data if data else None)
            for event in protocol.events():
                if isinstance(event,events.TextMessage):frames.append(event.data)
                if isinstance(event,events.CloseConnection):
                    close=event.code
                    if data:peer.sendall(protocol.send(event.response()))
        assert frames==[payload.hex()]
        assert close==1000


@pytest.mark.parametrize('fragmented',[False,True])
def test_read_limit_rejects_declared_size_before_receiving_body(fragmented):
    app=FastAPI();messages=[]
    @app.websocket('/')
    async def endpoint(ws:WebSocket):
        await ws.accept();messages.append(await ws.receive())
    with serve_relay(app) as address, socket.create_connection(address,timeout=1) as peer:
        protocol=WSConnection(ConnectionType.CLIENT)
        peer.sendall(protocol.send(events.Request(host='localhost',target='/')))
        accepted=False
        while not accepted:
            protocol.receive_data(peer.recv(65536))
            accepted=any(isinstance(event,events.AcceptConnection) for event in protocol.events())
        mask=b'abcd'
        if fragmented:
            payload=b'x'*32768
            peer.sendall(b'\x01\xfe\x80\x00'+mask+bytes(value^mask[i%4] for i,value in enumerate(payload)))
            peer.sendall(b'\x80\xfe\x80\x01'+mask)
        else:
            peer.sendall(b'\x81\xff'+(65537).to_bytes(8,'big')+mask)
        closes=[]
        while not closes:
            data=peer.recv(65536);protocol.receive_data(data if data else None)
            closes=[event for event in protocol.events() if isinstance(event,events.CloseConnection)]
        assert closes[0].code==1009 and not closes[0].reason
    assert messages and messages[0].get('workpal.too_large') is True


def test_canonical_transport_does_not_negotiate_compression():
    from wsproto.extensions import PerMessageDeflate
    app=FastAPI()
    @app.websocket('/')
    async def endpoint(ws:WebSocket):
        await ws.accept();await ws.close()
    with serve_relay(app) as address, socket.create_connection(address,timeout=3) as peer:
        protocol=WSConnection(ConnectionType.CLIENT)
        peer.sendall(protocol.send(events.Request(host='localhost',target='/',extensions=[PerMessageDeflate()])))
        accepted=[]
        while not accepted:
            protocol.receive_data(peer.recv(65536))
            accepted=[event for event in protocol.events() if isinstance(event,events.AcceptConnection)]
        assert accepted[0].extensions==[]


def test_auth_error_frame_is_followed_by_tcp_close_without_close_control():
    from workpal_backend.realtime.first_message_auth import send_auth_error
    app=FastAPI()
    @app.websocket('/')
    async def endpoint(ws:WebSocket):
        await ws.accept();await send_auth_error(ws,'invalid token')
    with serve_relay(app) as address, socket.create_connection(address,timeout=3) as peer:
        protocol=WSConnection(ConnectionType.CLIENT)
        peer.sendall(protocol.send(events.Request(host='localhost',target='/')))
        frames=[];closes=[]
        while True:
            data=peer.recv(65536)
            if not data:break
            protocol.receive_data(data)
            for event in protocol.events():
                if isinstance(event,events.TextMessage):frames.append(event.data)
                if isinstance(event,events.CloseConnection):closes.append(event.code)
        assert frames==['{"error":"invalid token"}']
        assert closes==[]


@pytest.mark.parametrize('proxy,allowed',[('127.0.0.0/8',True),('10.0.0.0/8',False)])
def test_origin_proxy_trust_uses_tcp_peer_before_forwarded_address_rewrite(proxy,allowed):
    from workpal_backend.realtime.origins import OriginPolicy
    from workpal_backend.realtime.routes import origin_allowed,deny_origin
    app=FastAPI();app.state.ws_origin_policy=OriginPolicy([], [proxy])
    @app.websocket('/')
    async def endpoint(ws:WebSocket):
        if not origin_allowed(ws):
            await deny_origin(ws)
            return
        await ws.accept();await ws.close()
    with serve_relay(app) as address, socket.create_connection(address,timeout=3) as peer:
        protocol=WSConnection(ConnectionType.CLIENT)
        peer.sendall(protocol.send(events.Request(host='internal',target='/',extra_headers=[
            (b'origin',b'https://public'),(b'x-forwarded-host',b'public'),(b'x-forwarded-for',b'10.1.2.3')])))
        result=None
        while result is None:
            data=peer.recv(65536);assert data;protocol.receive_data(data)
            for event in protocol.events():
                if isinstance(event,events.AcceptConnection):result=True
                elif isinstance(event,events.RejectConnection):
                    assert event.status_code==403
                    result=False
        assert result is allowed
