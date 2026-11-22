"""Original Go deliverEnvelope dispatch into actual Hub and optional sinks."""
from pathlib import Path
import asyncio,base64,hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.realtime.hub import Hub,Connection
from workpal_backend.realtime.relay_delivery import deliver_envelope
from workpal_backend.realtime.relay_envelope import Envelope

def run(output):
    fixtures=[]
    for scope,identity,exclude in [('workspace','w',''),('workspace','',''),('user','u','w'),('global','','w'),('chat','c',''),('custom','c',''),('unknown','c',''),('daemon_runtime','r',''),('wecom_outbound','i','')]:
        for frame in [b'{"type":"fixture"}',b'{"event_id":"original","x":1}',b'raw',b'']:
            for external in [False,True]:
                fixtures.append(dict(Scope=scope,ID=identity,Exclude=exclude,EventID='e',Frame=base64.b64encode(frame).decode(),External=external))
    fixtures.append(dict(Scope='global',ID='all',Exclude='',EventID='',Frame=base64.b64encode(b'{"x":1}').decode(),External=False))
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_relay_delivery"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/realtime/parity_delivery.go && cd /work && go build -mod=readonly -p=4 -o /out/relay-delivery-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/relay-delivery-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    async def observe(f):
        class Socket:
            def __init__(self):self.frames=[]
            async def send_text(self,raw):self.frames.append(base64.b64encode(raw.encode()).decode())
            async def close(self,code):pass
        h=Hub();clients=[];sockets=[];external=[]
        for w,u in [('w','u'),('w','v'),('x','u')]:
            socket=Socket();c=Connection(socket,lambda:None,w,u);h.register(c);clients.append(c);sockets.append(socket)
        h.subscribe(clients[0],'chat','c');h.subscribe(clients[1],'custom','c')
        def sink(kind):return lambda identity,raw,event:external.append([kind,identity,base64.b64encode(raw).decode(),event])
        envelope=Envelope(scope=f['Scope'],scope_id=f['ID'],workspace_id=f['Exclude'],event_id=f['EventID'],payload_json=base64.b64decode(f['Frame']))
        try:
            for _ in range(2):deliver_envelope(h,envelope,daemon_runtime=sink('daemon') if f['External'] else None,wecom_outbound=sink('wecom') if f['External'] else None)
            await asyncio.gather(*(c._writer.flush() for c in clients))
            return dict(frames=[s.frames for s in sockets],external=external)
        finally:await h.close()
    python=[asyncio.run(observe(f)) for f in fixtures]
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/realtime/redis_relay.go','server/go/internal/realtime/hub.go',
             'server/tests/parity/go_relay_delivery/main.go','server/tests/parity/go_relay_delivery/wrapper.go',
             'server/src/workpal_backend/realtime/relay_delivery.py','server/src/workpal_backend/realtime/relay_frame.py',
             'server/src/workpal_backend/realtime/relay_envelope.py','server/src/workpal_backend/realtime/hub.py']
    Path(output).write_text(json.dumps(dict(scope='Actual original Go deliverEnvelope dispatch to Hub send channels and optional daemon/wecom sinks. Compare all routed frame bytes, existing ID preservation, empty payload/scope handling and repeated delivery dedup; Python actual Hub/writer with socket callback. No Redis lifecycle, external daemon integrations, invalid UTF8 transport or timing certified.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},binary_sha256=hashlib.sha256((binaries/'relay-delivery-oracle').read_bytes()).hexdigest()),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
