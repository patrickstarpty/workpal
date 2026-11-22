"""Original Go retention normalization and refresh-claim state machine."""
from pathlib import Path
import hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.realtime.stream_retention import RetentionConfig,TTLRefresher

def run(output):
    configurations=[[0,0,0,0,0],[-1,-1,-1,-1,-1],[7,3,3,3,3],[7,1,1,0,0],[7,2,2,0,0],
        [200,100,99,20,30],[200,100,100,99,100],[1,600000000000,900000000000,30000000000,60000000000],
        [1,600000000000,900000000000,900000000000,900000000001]]
    configurations.extend([[1,(1<<63)-1,0,0,0],[1,(1<<63)-300_000_000_000,0,0,0]])
    fixtures=[]
    for config in configurations:
        for enabled in [False,True]:
            normalized=RetentionConfig(*config,enabled).with_defaults()
            interval=normalized.refresh_ns
            steps=[dict(Op=op,Key=key,At=at) for op,key,at in [
                ('claim','a',100),('claim','a',100),('claim','b',100),('claim','a',99),
                ('claim','a',100+interval-1),('claim','a',100+interval),
                ('release','a',100),('claim','a',100+interval),
                ('stale','',100+interval),('claim','a',100+interval),('claim','b',100+interval),
                ('release','a',100+interval),('claim','a',100+interval),('forget','a',0),('claim','a',0)]]
            fixtures.append(dict(Config=config,Enabled=enabled,Steps=steps))
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_retention"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/realtime/parity_retention.go && cd /work && go build -mod=readonly -p=4 -o /out/retention-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/retention-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    python=[]
    for f in fixtures:
        c=RetentionConfig(*f['Config'],f['Enabled']).with_defaults()
        r=TTLRefresher(c.ttl_ns,c.refresh_ns)
        results=[]
        for s in f['Steps']:
            op,key,at=s['Op'],s['Key'],s['At']
            if op=='claim':value=r.claim(key,at)
            elif op=='release':value=r.release(key,at)
            elif op=='forget':value=r.forget(key)
            else:value=r.forget_stale(at)
            results.append(value)
        python.append(dict(config=[c.max_len,c.trim_ns,c.ttl_ns,c.refresh_ns,c.maintenance_ns],enabled=c.enabled,results=results))
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/realtime/stream_retention.go','server/go/internal/realtime/sharded_stream_relay.go',
             'server/tests/parity/go_retention/main.go','server/tests/parity/go_retention/wrapper.go',
             'server/src/workpal_backend/realtime/stream_retention.py']
    Path(output).write_text(json.dumps(dict(scope='Actual Go retention config normalization and claim/release/forget/stale transitions. No Redis I/O, maintenance scheduling, or publisher lifecycle certified.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},binary_sha256=hashlib.sha256((binaries/'retention-oracle').read_bytes()).hexdigest()),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
