"""Compare actual Go and Python loopback WebSocket writer observations."""
from pathlib import Path
import base64,asyncio,hashlib,json,queue,socket,sys,tempfile,threading,time
from run_writer_parity import run as run_go
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from fastapi import FastAPI,WebSocket
import uvicorn
from wsproto import WSConnection,ConnectionType,events
from workpal_backend.realtime.hub import Connection
from workpal_backend.realtime.transport import RelayWebSocketProtocol


def read_opaque_frames(peer):
    """Read unmasked server text fragments without imposing UTF-8 validation."""
    buffer=b''
    while b'\r\n\r\n' not in buffer:
        data=peer.recv(65536)
        if not data:raise RuntimeError('connection closed before handshake')
        buffer+=data
    header,buffer=buffer.split(b'\r\n\r\n',1)
    assert header.startswith(b'HTTP/1.1 101')
    def take(count):
        nonlocal buffer
        while len(buffer)<count:
            data=peer.recv(65536)
            if not data:raise RuntimeError('connection closed within frame')
            buffer+=data
        result,buffer=buffer[:count],buffer[count:]
        return result
    frames=[];payload=b''
    while True:
        first,second=take(2)
        assert first & 0x70 == 0 and second & 0x80 == 0
        length=second & 0x7f
        if length==126:length=int.from_bytes(take(2),'big')
        elif length==127:length=int.from_bytes(take(8),'big')
        raw=take(length);opcode=first & 15
        if opcode==8:
            return frames, int.from_bytes(raw[:2],'big') if raw else 1005
        assert opcode in (0,1)
        payload+=raw
        if first & 0x80:
            frames.append(base64.b64encode(payload).decode());payload=b''


def observe(fixture):
    app=FastAPI();result=queue.Queue()
    @app.websocket('/')
    async def endpoint(ws:WebSocket):
        await ws.accept();loop=asyncio.get_running_loop();lookups=0;injected=False
        async def inject():return connection.try_send(b'late')
        def check():
            nonlocal lookups,injected
            lookups+=1
            if fixture['Inject'] and lookups==1:
                injected=asyncio.run_coroutine_threadsafe(inject(),loop).result(timeout=2)
            if fixture['DenyOn'] and lookups>=fixture['DenyOn']:raise PermissionError('revoked')
        connection=Connection(ws,check,'w','u')
        payloads=[base64.b64decode(raw) for raw in fixture['Frames']] if 'Frames' in fixture else [str(i).encode() for i in range(fixture['Count'])]
        accepted=[connection.try_send(raw) for raw in payloads]
        after_finish=None
        if fixture.get('Finish'):
            connection.finish();after_finish=connection.try_send(b'after')
        await connection._writer.flush()
        await connection.close()
        result.put(dict(accepted=accepted,lookups=lookups,injected=injected,after_finish=after_finish))
    listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen()
    server=uvicorn.Server(uvicorn.Config(app,ws=RelayWebSocketProtocol,lifespan='off',log_level='error',ws_ping_interval=None))
    thread=threading.Thread(target=server.run,kwargs={'sockets':[listener]},daemon=True);thread.start()
    try:
        deadline=time.monotonic()+5
        while not server.started:
            if not thread.is_alive() or time.monotonic()>deadline:raise RuntimeError('Python transport failed to start')
            time.sleep(.005)
        frames=[];close_code=0
        with socket.create_connection(listener.getsockname(),timeout=5) as peer:
            protocol=WSConnection(ConnectionType.CLIENT)
            peer.sendall(protocol.send(events.Request(host='localhost',target='/')))
            if 'Frames' in fixture:
                frames,close_code=read_opaque_frames(peer)
            while 'Frames' not in fixture:
                data=peer.recv(65536)
                protocol.receive_data(data if data else None)
                for event in protocol.events():
                    if isinstance(event,events.TextMessage):frames.append(event.data)
                    if isinstance(event,events.CloseConnection):
                        close_code=event.code
                        if data:peer.sendall(protocol.send(event.response()))
                if close_code or not data:break
        observation=result.get(timeout=3)
        observation.update(frames=frames,close_code=close_code if fixture.get('Finish') else 0)
        return observation
    finally:
        server.should_exit=True;thread.join(5);listener.close()
        if thread.is_alive():raise RuntimeError('Python transport did not stop')


def run(output):
    with tempfile.TemporaryDirectory(prefix='workpal-writer-wire-') as tmp:
        path=Path(tmp)/'go.json'
        if run_go(path):raise RuntimeError('base Go writer differential failed')
        base=json.loads(path.read_text())
    python=[observe(f) for f in base['fixtures']]
    mismatches=[i for i,(a,b) in enumerate(zip(base['go'],python)) if a!=b]
    sources=['server/src/workpal_backend/realtime/transport.py','server/src/workpal_backend/realtime/hub.py',
             'server/src/workpal_backend/cli.py','server/tools/run_writer_transport_parity.py']
    hashes=dict(base['source_sha256']);hashes.update({p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources})
    Path(output).write_text(json.dumps(dict(scope='Actual Go Gorilla and Python canonical uvicorn/wsproto protocol on isolated loopback sockets, all original writer fixtures. Compare text frames, queue acceptance, membership lookup counts, late injection, and finish close codes including abrupt denial1006 vs empty1005. Non-finish teardown code normalized to0 in both. Includes opaque invalid UTF8 text bytes and short/extended payload lengths; raw parser compares logical messages independently of fragmentation. No full app handshake, ping/deadline timing, slow-peer backpressure or global Hub fanout certification.',fixtures=base['fixtures'],go=base['go'],python=python,mismatches=mismatches,source_sha256=hashes,binary_sha256=base['binary_sha256']),indent=2)+'\n')
    print(json.dumps(dict(wire_cases=len(python),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
