"""Original Go firstMessageAuth versus Python on real loopback WebSockets."""
from pathlib import Path
import base64,hashlib,json,queue,socket,sys,threading,time
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from fastapi import FastAPI,WebSocket
import uvicorn
from wsproto import WSConnection,ConnectionType,events
from workpal_backend.realtime.first_message_auth import read_first_auth
from workpal_backend.realtime.transport import RelayWebSocketProtocol


def observe(f):
    app=FastAPI();results=queue.Queue()
    @app.websocket('/')
    async def endpoint(ws:WebSocket):
        await ws.accept()
        counted=[]
        token,error,closed=await read_first_auth(ws,lambda:counted.append(True))
        # Go returns the encoded error payload; Python returns its detail to
        # the route, whose send_json wraps it in the same error object.
        payload=json.dumps({'error':error},separators=(',',':')) if error else ''
        results.put(dict(token=token,error=payload,closed=closed,too_large=len(counted)))
        if not closed:await ws.close()
    listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen()
    server=uvicorn.Server(uvicorn.Config(app,ws=RelayWebSocketProtocol,lifespan='off',log_level='error',ws_ping_interval=None))
    thread=threading.Thread(target=server.run,kwargs={'sockets':[listener]},daemon=True);thread.start()
    try:
        deadline=time.monotonic()+5
        while not server.started:
            if not thread.is_alive() or time.monotonic()>deadline:raise RuntimeError('Python transport failed to start')
            time.sleep(.005)
        with socket.create_connection(listener.getsockname(),timeout=3) as peer:
            protocol=WSConnection(ConnectionType.CLIENT)
            peer.sendall(protocol.send(events.Request(host='localhost',target='/')))
            accepted=False
            while not accepted:
                data=peer.recv(65536)
                if not data:raise RuntimeError('handshake closed')
                protocol.receive_data(data)
                accepted=any(isinstance(e,events.AcceptConnection) for e in protocol.events())
            if f.get('HeaderOnly'):
                first=0x82 if f['Binary'] else 0x81;mask=b'abcd'
                if f['Fragmented']:
                    peer.sendall(bytes([first&0x7f,0xfe,0x80,0])+mask+bytes(120^mask[i%4] for i in range(32768)))
                    peer.sendall(b'\x80\xfe\x80\x01'+mask)
                else:
                    peer.sendall(bytes([first,0xff])+(65537).to_bytes(8,'big')+mask)
                return results.get(timeout=3)
            raw=base64.b64decode(f['Raw']);pieces=[raw]
            if f['Fragmented']:pieces=[raw[:16],raw[16:]]
            for i,piece in enumerate(pieces):
                opcode=(2 if f['Binary'] else 1) if i==0 else 0
                first=opcode|(128 if i==len(pieces)-1 else 0);length=len(piece)
                header=bytes([first,128|length]) if length<126 else bytes([first,128|126])+length.to_bytes(2,'big') if length<65536 else bytes([first,128|127])+length.to_bytes(8,'big')
                mask=b'abcd';peer.sendall(header+mask+bytes(value^mask[n%4] for n,value in enumerate(piece)))
            return results.get(timeout=3)
    finally:
        server.should_exit=True;thread.join(5);listener.close()
        if thread.is_alive():raise RuntimeError('Python transport did not stop')


def run(output):
    raws=[b'',b'null',b'[]',b'{',b'{"type":"auth","payload":{"token":"a"}}',
          b'{"TYPE":"auth","PAYLOAD":{"TOKEN":"a"}}',
          b'{"type":"auth","payload":{"token":"a"},"payload":null}',
          b'{"type":"auth","payload":{"token":"a"},"payload":{}}',
          b'{"type":"auth","payload":{"token":"a","token":null}}',
          b'{"type":"auth","payload":{"token":"a","token":"b"}}',
          b'{"type":"auth","payload":{"token":"\xff"}}',
          b'{"type":"auth","payload":{"token":"\xed\xa0\x80"}}',
          b'{"type":3,"type":"auth","payload":{"token":"a"}}',
          b'{"type":"auth","payload":{"token":3,"token":"a"}}',
          b'{"type":"auth","payload":3,"payload":{"token":"a"}}',
          b'{"type":"auth","payload":[]}',b'{"type":"auth","payload":{"token":""}}',
          b'{"type":"auth","payload":{"token":" \\u0000 "}}',b'x'*65536,b'x'*65537]
    fixtures=[dict(Raw=base64.b64encode(raw).decode(),Binary=binary,Fragmented=fragmented) for raw in raws for binary,fragmented in [(False,False),(True,False),(False,True)]]
    fixtures.extend(dict(Raw='',Binary=binary,Fragmented=fragmented,HeaderOnly=True) for binary in [False,True] for fragmented in [False,True])
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_first_auth"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/realtime/parity_first_auth.go && cd /work && go build -mod=readonly -p=4 -o /out/first-auth-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/first-auth-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    python=[observe(f) for f in fixtures]
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/realtime/hub.go','server/tests/parity/go_first_auth/main.go',
             'server/tests/parity/go_first_auth/wrapper.go','server/src/workpal_backend/realtime/first_message_auth.py',
             'server/src/workpal_backend/realtime/frame_decode.py','server/src/workpal_backend/realtime/transport.py',
             'server/tools/run_first_auth_parity.py']
    Path(output).write_text(json.dumps(dict(scope='Original Go firstMessageAuth vs actual Python ASGI read_first_auth on loopback sockets. Text/binary/fragmented frames, invalid UTF8, typed JSON duplicate/null semantics and 64KiB size boundary including header-only rejection and cumulative fragmented lengths; compare token/error payload/closed/size metrics. No token verification, origin/cookie/membership handshake, read timeout timing or full route response certification.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(wire_cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
