import asyncio
import json
from workpal_backend.realtime.hub import Connection
from test_realtime import live

class Socket:
    def __init__(self):self.text=[];self.closed=False
    async def send_json(self,frame):self.text.append(json.dumps(frame,ensure_ascii=False,separators=(',',':')))
    async def send_text(self,raw):self.text.append(raw)
    async def close(self,code):self.closed=True


def test_connection_sends_go_map_bytes_without_newline():
    async def run():
        ws=Socket();c=Connection(ws,lambda:None,'w','u')
        await c.send({'type':'fixture','payload':{'z':'<>&\u2028\u2029','a':1e-7,'negative':-0.0}})
        assert ws.text==['{"payload":{"a":1e-7,"negative":-0,"z":"\\u003c\\u003e\\u0026\\u2028\\u2029"},"type":"fixture"}']
        assert not ws.closed
    asyncio.run(run())


def test_bad_serialization_drops_frame_without_closing_connection():
    async def run():
        ws=Socket();checked=[];c=Connection(ws,lambda:checked.append(True),'w','u')
        await c.send({'payload':float('nan')})
        assert ws.text==[] and not ws.closed and checked==[]
        await c.send({'type':'pong'})
        assert ws.text==['{"type":"pong"}']
    asyncio.run(run())


def test_real_websocket_ack_is_go_order_and_escaped(live):
    client,app,login,workspace=live
    with client.websocket_connect('/ws?workspace_slug=realtime') as ws:
        ws.send_json(dict(type='unsubscribe',payload={'scope':'chat','id':'<>&'}))
        assert ws.receive_text()=='{"payload":{"id":"\\u003c\\u003e\\u0026","scope":"chat"},"type":"unsubscribe_ack"}'
