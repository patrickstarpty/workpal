"""Original Go DualWriteBroadcaster with actual Hub queues and loopback."""
from pathlib import Path
import asyncio,base64,hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.realtime.hub import Hub,Connection
from workpal_backend.realtime.relay_modes import DualWriteBroadcaster
from workpal_backend.realtime.relay_envelope import new_envelope
from workpal_backend.realtime.relay_delivery import deliver_envelope

def run(output):
    fixtures=[]
    operations=[('scope','workspace','w',False),('scope','chat','c',False),('scope','global','all',False),('scope','global','all',True),('scope','user','u',False),('scope','workspace_member','w:u',False),('scope','daemon_runtime','r',False),('scope','wecom_outbound','i',False),('scope','','',False),('workspace','','w',False),('user','','u',False),('global','','',False)]
    for method,scope,identity,room in operations:
        for raw in [b'{"type":"fixture"}',b'{"event_id":"existing","type":"fixture"}',b'opaque\xff']:
            for loopback in [False,True]:
                for failure in [False,True]:
                    fixtures.append(dict(Method=method,Scope=scope,ID=identity,GlobalRoom=room,Exclude=['w','ignored'],Frame=base64.b64encode(raw).decode(),Loopback=loopback,Failure=failure))
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_dual_write"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/realtime/parity_dual.go && cd /work && go build -mod=readonly -p=4 -o /out/dual-write-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/dual-write-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    async def observe(f):
        h=Hub();clients=[];calls=[];before=[]
        class Socket:
            async def close(self,code):pass
        for workspace,user in [('w','u'),('w','v'),('x','u')]:
            c=Connection(Socket(),lambda:None,workspace,user);h.register(c);clients.append(c)
        h.subscribe(clients[0],'chat','c')
        if f['GlobalRoom']:h.subscribe(clients[0],'global','all')
        class Publisher:
            async def publish_with_id(self,scope,identity,exclude,frame,event_id):
                before.extend(c._writer._queue.qsize() for c in clients)
                calls.append([scope,identity,exclude,base64.b64encode(frame).decode(),event_id])
                if f['Loopback']:deliver_envelope(h,new_envelope('node',scope,identity,exclude,frame,event_id))
                if f['Failure']:raise RuntimeError('unavailable')
        d=DualWriteBroadcaster(h,Publisher(),id_factory=lambda:'EVENT');raw=base64.b64decode(f['Frame'])
        try:
            if f['Method']=='scope':await d.broadcast_to_scope(f['Scope'],f['ID'],raw)
            elif f['Method']=='workspace':await d.broadcast_to_workspace(f['ID'],raw)
            elif f['Method']=='user':await d.send_to_user(f['ID'],raw,*f['Exclude'])
            else:await d.broadcast(raw)
            queues=[]
            for c in clients:
                one=[];queue=c._writer._queue
                while not queue.empty():one.append(base64.b64encode(queue.get_nowait()).decode());queue.task_done()
                queues.append(one)
            return dict(calls=calls,before=before,queues=queues,sent=h.fanout_metrics.messages_sent)
        finally:await h.close()
    python=[asyncio.run(observe(f)) for f in fixtures]
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/realtime/redis_relay.go','server/go/internal/realtime/hub.go','server/tests/parity/go_dual_write/main.go','server/tests/parity/go_dual_write/wrapper.go','server/src/workpal_backend/realtime/relay_modes.py','server/src/workpal_backend/realtime/hub.py','server/src/workpal_backend/realtime/relay_delivery.py','server/src/workpal_backend/realtime/relay_frame.py']
    Path(output).write_text(json.dumps(dict(scope='Actual Go DualWriteBroadcaster and Hub queues vs Python Hub/writer queues. Local-before-publish, route-specific immediate fanout, loopback dedup, first exclusion, failed writes and opaque/existing-ID frames. Random generated IDs normalized to EVENT. No actual wire or Redis transport certification.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
