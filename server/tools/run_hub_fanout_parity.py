"""Original Go Hub raw fanout, dedup and slow-queue eviction."""
from pathlib import Path
import asyncio,hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.realtime.hub import Hub,Connection

def run(output):
    clients=[dict(Workspace=w,User=u,Preload=0) for w,u in [('w','u'),('w','v'),('x','u'),('','')]]
    def action(kind='scope',scope='workspace',identity='w',exclude='',frame='frame',event='',client=0):return dict(Kind=kind,Scope=scope,ID=identity,Exclude=exclude,Frame=frame,EventID=event,Client=client)
    sequences=[
        [action()],
        [action(event='e'),action(kind='user',identity='u',event='e'),action(kind='global',event='e')],
        [action(kind='user',identity='u',exclude='w'),action(kind='global',exclude='x')],
        [action(kind='unsubscribe',scope='user',identity='u'),action(kind='user',identity='u')],
        [action(kind='subscribe',scope='chat',identity='c'),action(scope='chat',identity='c')],
        [action(scope=''),action(identity=''),action(kind='global')],
        [action(kind='global',event=str(i)) for i in range(257)],
        [action(kind='global',event='same') for i in range(257)],
        [action(kind='global',event=str(i)) for i in range(129)]+[action(kind='global',event='0')],
    ]
    fixtures=[dict(Clients=clients,Actions=sequence) for sequence in sequences]
    fixtures.append(dict(Clients=[dict(Workspace='w',User='u',Preload=256),dict(Workspace='x',User='v',Preload=0)],Actions=[action(kind='global',event='e')]))
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_hub_fanout"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/realtime/parity_fanout.go && cd /work && go build -mod=readonly -p=4 -o /out/hub-fanout-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/hub-fanout-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    async def observe(f):
        class Socket:
            def __init__(self):self.frames=[]
            async def send_text(self,raw):self.frames.append(raw)
            async def close(self,code):pass
        h=Hub();clients=[];sockets=[]
        try:
            for v in f['Clients']:
                socket=Socket();c=Connection(socket,lambda:None,v['Workspace'],v['User']);h.register(c)
                for _ in range(v['Preload']):c.try_send(b'preloaded')
                clients.append(c);sockets.append(socket)
            for a in f['Actions']:
                kind=a['Kind']
                if kind=='scope':h.broadcast_to_scope(a['Scope'],a['ID'],a['Frame'].encode(),a['EventID'])
                elif kind=='user':h.send_to_user(a['ID'],a['Frame'].encode(),a['Exclude'],a['EventID'])
                elif kind=='global':h.broadcast_all(a['Frame'].encode(),a['Exclude'],a['EventID'])
                elif kind=='subscribe':h.subscribe(clients[a['Client']],a['Scope'],a['ID'])
                else:h.unsubscribe(clients[a['Client']],a['Scope'],a['ID'])
            present=[c in h.connections for c in clients]
            closed=[c._writer._finishing for c in clients]
            rooms=[list(r) for r in sorted(h.local_scopes())]
            await asyncio.gather(*(c._writer.flush() for c in clients))
            m=h.fanout_metrics
            return dict(frames=[s.frames for s in sockets],present=present,send_closed=closed,rooms=rooms,metrics=[m.messages_sent,m.messages_dropped,m.slow_evictions])
        finally:await h.close()
    python=[asyncio.run(observe(f)) for f in fixtures]
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/realtime/hub.go','server/go/internal/realtime/membership.go',
             'server/tests/parity/go_hub_fanout/main.go','server/tests/parity/go_hub_fanout/wrapper.go',
             'server/src/workpal_backend/realtime/hub.py','server/src/workpal_backend/realtime/writer.py','server/src/workpal_backend/realtime/dedup.py']
    Path(output).write_text(json.dumps(dict(scope='Actual original Go Hub scope/user/global raw fanout, per-client dedup, 256-channel overflow eviction and counters. Python actual Hub/writer with socket callback. Compare queued/delivered bytes, connection presence, closed send state, unordered rooms and sent/dropped/slow counters. No full metrics endpoint, membership removal transport, live Redis or timing certification.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},binary_sha256=hashlib.sha256((binaries/'hub-fanout-oracle').read_bytes()).hexdigest()),indent=2)+'\n')
    print(json.dumps(dict(scripts=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
