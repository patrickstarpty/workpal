"""Original Go RedisRelay Start/Stop/Wait against cancellable Redis IO."""
from pathlib import Path
import asyncio,hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.realtime.redis_relay import RedisRelay
from workpal_backend.realtime.hub import Hub

def run(output):
    fixtures=[dict(Separate=separate,Failure=failure) for separate in [False,True] for failure in ['', 'write', 'read']]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_redis_relay_owner"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/realtime/parity_owner.go && cd /work && go build -mod=readonly -p=4 -o /out/redis-relay-owner-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/redis-relay-owner-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    async def observe(f):
        calls=[];heartbeat=asyncio.Event();scan=asyncio.Event()
        class Client:
            def __init__(self,name):self.name=name
            async def ping(self):
                calls.append(self.name)
                if f['Failure']==self.name:raise RuntimeError('ping failed')
            async def set(self,*args,**kwargs):
                heartbeat.set();await asyncio.Event().wait()
            async def scan(self,*args,**kwargs):
                scan.set();await asyncio.Event().wait()
        write=Client('write');read=Client('read') if f['Separate'] else write
        hub=Hub();r=RedisRelay(hub,write,read_client=read);parent=asyncio.Event()
        try:
            await r.start(parent)
            connected=r.maintenance.metrics.connected
            await asyncio.wait_for(heartbeat.wait(),1);await asyncio.wait_for(scan.wait(),1)
            r.stop();stopped_parent=parent.is_set();parent.set();await asyncio.wait_for(r.wait(),1)
            return dict(pings=calls,connected=connected,stop_canceled_parent=stopped_parent,joined=not r._background,final_connected=r.maintenance.metrics.connected,retention_errors=r.maintenance.metrics.retention_errors)
        finally:
            parent.set();r.stop();await r.wait();await hub.close()
    python=[asyncio.run(observe(f)) for f in fixtures]
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/realtime/redis_relay.go','server/src/workpal_backend/realtime/redis_relay.py','server/src/workpal_backend/realtime/relay_consumers.py','server/src/workpal_backend/realtime/relay_maintenance.py','server/tests/parity/go_redis_relay_owner/main.go','server/tests/parity/go_redis_relay_owner/wrapper.go']
    Path(output).write_text(json.dumps(dict(scope='Original Go Start ping order and initial connected state, immediate maintenance entry, Stop leaves parent active, Wait joins after parent cancellation. Empty Hub, cancellable Redis boundary. Includes final connected state and retention error count for blocked heartbeat/SCAN cancellation. Does not certify all event ordering, repeated Start, or full application integration.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
