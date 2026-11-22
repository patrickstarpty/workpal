"""Compare original Go fixed-shard maintenance at the Redis command boundary."""
from pathlib import Path
import asyncio, hashlib, json, sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.realtime.sharded_config import ShardedConfig
from workpal_backend.realtime.sharded_publisher import ShardedPublisher
from workpal_backend.realtime.sharded_maintenance import ShardedMaintenance

def run(output):
    fixtures=[dict(Enabled=enabled,TTL=ttl,Failure=failure,Missing=missing,Stop=stop)
              for enabled in [False,True] for ttl in [-2,-1,0,5000]
              for failure,missing,stop in [(f,False,False) for f in ['', 'exists','trim','pttl','expire','persist','gone','length','memory','stats']]+[('',True,False),('',False,True)]]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_sharded_maintenance"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/realtime/parity_sharded_maintenance.go && cd /work && go build -mod=readonly -p=4 -o /out/sharded-maintenance-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/sharded-maintenance-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    async def observe(f):
        calls=[]
        def fail(name):
            if f['Failure']==name:raise RuntimeError(name+' failed')
        class Client:
            async def exists(self,key):
                calls.append(['exists',key]);fail('exists');return not f['Missing']
            async def xtrim(self,key,**kwargs):
                assert kwargs['approximate'] is False
                calls.append(['trim',key,kwargs['minid']]);fail('trim');return 2
            async def pttl(self,key):
                calls.append(['pttl',key]);fail('pttl');return f['TTL']
            async def pexpire(self,key,ttl):
                calls.append(['expire',key,ttl]);fail('expire');return f['Failure']!='gone'
            async def persist(self,key):
                calls.append(['persist',key]);fail('persist');return f['Failure']!='gone'
            async def xlen(self,key):
                calls.append(['length',key]);fail('length');return 3
            async def info(self,section):
                calls.append(['info',section]);fail(section)
                return dict(used_memory=17,maxmemory=19,evicted_keys=23)
        p=ShardedPublisher(Client(),'n',config=ShardedConfig(shards=2,enabled=f['Enabled']))
        m=ShardedMaintenance(p,clock_ns=lambda:1000_000_000_000)
        p.seen[0]=True;p.ttl.claim('ws:relay:shard:0',p.ttl.clock_ns())
        p.metrics.set_streams_without_ttl('sharded',7)
        stop=asyncio.Event()
        if f['Stop']:stop.set()
        await m.maintain_once(stop)
        return dict(calls=calls,seen=p.seen,generation=m.generations,metrics=p.metrics.snapshot())
    python=[asyncio.run(observe(f)) for f in fixtures]
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/realtime/sharded_stream_relay.go','server/go/internal/realtime/stream_retention.go',
             'server/tests/parity/go_sharded_maintenance/main.go','server/tests/parity/go_sharded_maintenance/wrapper.go',
             'server/src/workpal_backend/realtime/sharded_maintenance.py','server/src/workpal_backend/realtime/sharded_publisher.py',
             'server/src/workpal_backend/realtime/sharded_config.py','server/src/workpal_backend/realtime/sharded_reader.py',
             'server/src/workpal_backend/realtime/relay_maintenance.py','server/src/workpal_backend/realtime/stream_retention.py',
             'server/src/workpal_backend/realtime/relay_metrics.py']
    Path(output).write_text(json.dumps(dict(scope='Original Go maintainStreams command order, TTL repair errors, absent streams, canceled parent, generation changes and complete Redis metrics. Redis boundary fixtures; INFO map uses normal Redis numeric values. No scheduler, real Go Redis IO or arbitrary malformed INFO certification.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
