"""Original Go Hub subscription and first/last callback transitions."""
from pathlib import Path
import hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.realtime.hub import Hub,Connection

def run(output):
    clients=[dict(Workspace=w,User=u,Stopped=stopped) for w,u,stopped in [('w','u',False),('w','v',False),('other','u',False),('','u',False),('w','',False),('w','stopped',True)]]
    def steps(values):return [dict(Op=o,Client=c,Scope=s,ID=i) for o,c,s,i in values]
    fixtures=[dict(Clients=clients,Steps=steps([
        ('subscribe',0,'chat','c'),('register',0,'',''),('register',1,'',''),('register',2,'',''),
        ('register',3,'',''),('register',4,'',''),('register',5,'',''),('register',0,'',''),
        ('subscribe',0,'chat','c'),('subscribe',0,'chat','c'),('subscribe',1,'chat','c'),
        ('unsubscribe',0,'chat','c'),('unsubscribe',0,'chat','c'),('unsubscribe',1,'chat','c'),
        ('subscribe',0,'','x'),('subscribe',0,'chat',''),('unsubscribe',0,'',''),
        ('remove',0,'',''),('remove',0,'',''),('subscribe',0,'chat','c'),
        ('remove',1,'',''),('remove',2,'',''),('remove',3,'',''),('remove',4,'','')
    ])),dict(Clients=clients,Steps=steps([
        ('disable',0,'',''),('register',0,'',''),('enable',0,'',''),
        ('subscribe',0,'user','v'),('unsubscribe',0,'workspace','w'),
        ('subscribe',0,'workspace','w'),('remove',0,'','')
    ]))]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_hub_subscriptions"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/realtime/parity_subscriptions.go && cd /work && go build -mod=readonly -p=4 -o /out/hub-subscriptions-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/hub-subscriptions-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    python=[]
    for f in fixtures:
        h=Hub();clients=[];callbacks=[]
        def first(s,i):callbacks.append(['first',s,i])
        def last(s,i):callbacks.append(['last',s,i])
        h.set_subscription_callbacks(first,last)
        for c in f['Clients']:
            connection=Connection(None,lambda:None,c['Workspace'],c['User'])
            connection.rooms.clear() # Go Client starts with no subscriptions before register.
            connection.closed=c['Stopped'];clients.append(connection)
        observations=[]
        for s in f['Steps']:
            callbacks.clear();c=clients[s['Client']];op=s['Op'];result=None
            if op=='register':h.register(c)
            elif op=='remove':h.unregister(c)
            elif op=='subscribe':result=h.subscribe(c,s['Scope'],s['ID'])
            elif op=='unsubscribe':result=h.unsubscribe(c,s['Scope'],s['ID'])
            elif op=='disable':h.set_subscription_callbacks(None,None)
            else:h.set_subscription_callbacks(first,last)
            observations.append(dict(result=result,callbacks=sorted(callbacks) if op=='remove' else list(callbacks),rooms=[list(r) for r in sorted(h.local_scopes())],subscriptions=[[list(r) for r in sorted(c.rooms)] for c in clients],present=[c in h.connections for c in clients],metrics=h.metrics.snapshot()))
        python.append(observations)
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/realtime/hub.go','server/go/internal/realtime/membership.go',
             'server/tests/parity/go_hub_subscriptions/main.go','server/tests/parity/go_hub_subscriptions/wrapper.go',
             'server/src/workpal_backend/realtime/hub.py','server/src/workpal_backend/realtime/routes.py',
             'server/src/workpal_backend/realtime/metrics.py','server/src/workpal_backend/realtime/relay_metrics.py','server/go/internal/realtime/metrics.go']
    Path(output).write_text(json.dumps(dict(scope='Original Go register/subscribe/unsubscribe/remove and callback replacement. Rooms unordered; removal callback batch unordered due Go map iteration. Includes connection/subscription/room metric snapshots. No send channel shutdown, concurrent callback ordering, or transport lifecycle certification.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},binary_sha256=hashlib.sha256((binaries/'hub-subscriptions-oracle').read_bytes()).hexdigest()),indent=2)+'\n')
    print(json.dumps(dict(scripts=len(fixtures),observations=sum(len(f['Steps']) for f in fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
