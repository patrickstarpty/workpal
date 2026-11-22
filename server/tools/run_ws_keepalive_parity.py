"""Actual unmodified Go and Python 54s ping/60s read deadline observations."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import base64,hashlib,json,socket,sys,threading,time
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from fastapi import FastAPI,WebSocket
import uvicorn
from wsproto import WSConnection,ConnectionType,events
from workpal_backend.realtime.hub import Hub,Connection
from workpal_backend.realtime.transport import RelayWebSocketProtocol


def observe(pong):
    app=FastAPI()
    @app.websocket('/')
    async def endpoint(ws:WebSocket):
        await ws.accept();hub=Hub();connection=Connection(ws,lambda:None,'w','u');hub.register(connection)
        try:
            await connection.start_session()
            while (await ws.receive())['type']!='websocket.disconnect':pass
        finally:await hub.close()
    listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen()
    server=uvicorn.Server(uvicorn.Config(app,ws=RelayWebSocketProtocol,lifespan='off',log_level='error'))
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
                data=peer.recv(65536);assert data;protocol.receive_data(data)
                accepted=any(isinstance(e,events.AcceptConnection) for e in protocol.events())
            peer.settimeout(.1);start=time.monotonic();pings=[];sent=False;code=None
            while code is None:
                elapsed=time.monotonic()-start
                if elapsed>70:raise RuntimeError('Python read deadline did not close connection')
                if pong and not sent and elapsed>=2:
                    peer.sendall(protocol.send(events.Pong(payload=b'unsolicited')));sent=True
                try:data=peer.recv(65536)
                except TimeoutError:continue
                protocol.receive_data(data if data else None)
                for event in protocol.events():
                    if isinstance(event,events.Ping):pings.append(dict(payload=base64.b64encode(event.payload).decode(),at=time.monotonic()-start))
                    if isinstance(event,events.CloseConnection):code=event.code
            return dict(pings=pings,closed_at=time.monotonic()-start,close_code=code)
    finally:
        server.should_exit=True;thread.join(5);listener.close()
        if thread.is_alive():raise RuntimeError('Python transport did not stop')


def run(output):
    fixtures=[False,True]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_ws_keepalive"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/realtime/parity_ws_keepalive.go && cd /work && go build -mod=readonly -p=4 -o /out/ws-keepalive-oracle ./parity'])
    with ThreadPoolExecutor(max_workers=3) as pool:
        reference_run=pool.submit(command,['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
            '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
            '/out/ws-keepalive-oracle'],input=json.dumps(fixtures),timeout=85)
        python_runs=[pool.submit(observe,pong) for pong in fixtures]
        go=json.loads(reference_run.result().stdout);python=[future.result() for future in python_runs]
    def within(observation,pong):
        expected=62 if pong else 60
        return (len(observation['pings'])==1 and observation['pings'][0]['payload']==''
                and 53.5<=observation['pings'][0]['at']<=55.5
                and expected-.5<=observation['closed_at']<=expected+1.5 and observation['close_code']==1006)
    failures=[i for i,pong in enumerate(fixtures) if not within(go[i],pong) or not within(python[i],pong)]
    sources=['server/go/internal/realtime/hub.go','server/tests/parity/go_ws_keepalive/main.go','server/tests/parity/go_ws_keepalive/wrapper.go',
             'server/src/workpal_backend/realtime/transport.py','server/src/workpal_backend/realtime/hub.py','server/tools/run_ws_keepalive_parity.py']
    Path(output).write_text(json.dumps(dict(scope='Actual unmodified Go readPump/writePump and Python canonical transport on loopback sockets. One empty Ping at54s and read timeout at60s; unsolicited Pong at2s extends closure to62s without shifting Ping. Raw elapsed timings retained; both must independently meet documented scheduler windows (early tolerance0.5s/late1.5s). Go unregister boundary delays queue close until reader TCP close to remove graceful-close race. No all-scheduling or slow-peer write-deadline certification.',fixtures=fixtures,go=go,python=python,failures=failures,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),failures=failures,go=go,python=python)))
    return bool(failures)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
