import pytest


def test_auth_frame_matches_typed_struct_merging_and_replacement():
    from workpal_backend.realtime.first_message_auth import decode_auth_message
    assert decode_auth_message(b'{"TYPE":"auth","PAYLOAD":{"TOKEN":"a"},"payload":null}')=='a'
    assert decode_auth_message(b'{"type":"auth","payload":{"token":"a"},"payload":{}}')=='a'
    assert decode_auth_message(b'{"type":"auth","payload":{"token":"a","token":null}}')=='a'
    assert decode_auth_message(b'{"type":"auth","payload":{"token":"\xff"}}')=='\ufffd'
    for raw in [b'null',b'[]',b'{"type":"auth","payload":{}}',
                b'{"type":3,"type":"auth","payload":{"token":"a"}}',
                b'{"type":"auth","payload":{"token":3,"token":"a"}}',
                b'{"type":"auth","payload":3,"payload":{"token":"a"}}']:
        with pytest.raises(ValueError,match='expected auth message as first frame'):
            decode_auth_message(raw)


def test_first_auth_transport_disconnect_and_oversize_do_not_emit_auth_errors():
    import asyncio
    from workpal_backend.realtime.first_message_auth import read_first_auth
    async def run():
        counted=[]
        class Socket:
            message={}
            closes=[]
            async def receive(self):return self.message
            async def close(self,code):self.closes.append(code)
        socket=Socket()
        socket.message={'type':'websocket.disconnect','code':1009,'workpal.too_large':True}
        assert await read_first_auth(socket,lambda:counted.append(True)) == ('','',True)
        assert socket.closes==[] and counted==[True]
        socket.message={'type':'websocket.receive','bytes':b'x'*65537}
        assert await read_first_auth(socket,lambda:counted.append(True)) == ('','',True)
        assert socket.closes==[1009] and counted==[True,True]
        socket.message={'type':'websocket.disconnect','code':1009}
        assert await read_first_auth(socket) == ('','auth timeout or read error',False)
    asyncio.run(run())


def test_auth_error_always_aborts_even_when_error_write_fails():
    import asyncio
    from workpal_backend.realtime.first_message_auth import send_auth_error
    async def run():
        class Socket:
            scope={'extensions':{'workpal.websocket.abort':{}}}
            messages=[]
            async def send_json(self,value):raise OSError('closed')
            async def send(self,message):self.messages.append(message)
        socket=Socket()
        with pytest.raises(OSError):await send_auth_error(socket,'invalid token')
        assert socket.messages==[{'type':'websocket.close','workpal.abort':True}]
    asyncio.run(run())
