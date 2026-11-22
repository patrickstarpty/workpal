"""Compare original Go legacy sweeper with Python at the Redis command boundary."""
from pathlib import Path
from types import SimpleNamespace
import asyncio,hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.realtime.relay_publisher import RelayPublisher
from workpal_backend.realtime.relay_maintenance import RelayMaintenance
from workpal_backend.realtime.stream_retention import RetentionConfig

def run(output):
    fixtures=[dict(Enabled=enabled,TTL=ttl,Failure=failure)
              for enabled in [False,True] for ttl in [-2,-1,300]
              for failure in ['', 'trim', 'pttl', 'expire', 'persist', 'gone', 'scan']]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_relay_maintenance"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/realtime/parity_maintenance.go && cd /work && go build -mod=readonly -p=4 -o /out/relay-maintenance-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/relay-maintenance-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    async def observe(f):
        calls=[]
        class Client:
            page=0
            async def xtrim(self,key,**kwargs):
                calls.append(['trim',key,kwargs['minid']])
                if f['Failure']=='trim':raise RuntimeError('trim failed')
                return 2
            async def pttl(self,key):
                calls.append(['pttl',key])
                if f['Failure']=='pttl':raise RuntimeError('pttl failed')
                return f['TTL']
            async def pexpire(self,key,ttl):
                calls.append(['expire',key,ttl])
                if f['Failure']=='expire':raise RuntimeError('expire failed')
                return f['Failure']!='gone'
            async def persist(self,key):
                calls.append(['persist',key])
                if f['Failure']=='persist':raise RuntimeError('persist failed')
                return f['Failure']!='gone'
            async def scan(self,cursor,**kwargs):
                calls.append(['scan',cursor,kwargs['match'],kwargs['count']]);self.page+=1
                if f['Failure']=='scan' and self.page==2:raise RuntimeError('scan failed')
                return (7,['legacy']) if self.page==1 else (0,[])
        r=RelayMaintenance(SimpleNamespace(local_scopes=lambda: []),RelayPublisher(Client(),'node',retention=RetentionConfig(enabled=f['Enabled'])),clock_ns=lambda:1000_123_456_789)
        states=[]
        for _ in range(3):
            await r.sweep_once()
            states.append(dict(cursor=r.cursor,without=sorted(r.without_ttl),errors=r.metrics.retention_errors,trimmed=r.metrics.trimmed))
        return dict(calls=calls,states=states)
    python=[asyncio.run(observe(f)) for f in fixtures]
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    assert len(go)==len(python)
    sources=['server/go/internal/realtime/redis_relay.go','server/go/internal/realtime/stream_retention.go',
             'server/src/workpal_backend/realtime/relay_maintenance.py','server/src/workpal_backend/realtime/stream_retention.py',
             'server/tests/parity/go_relay_maintenance/main.go','server/tests/parity/go_relay_maintenance/wrapper.go']
    Path(output).write_text(json.dumps(dict(scope='Original Go legacy sweeper, empty local scopes, three scan passes, Redis boundary recorder. TTL modes, repair errors, cursor and observed sets. Does not certify heartbeat, real Redis IO, timeout/cancellation or periodic lifecycle.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
