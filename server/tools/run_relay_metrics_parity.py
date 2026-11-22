"""Compare the Redis portion of original Go realtime Metrics.Snapshot."""
from pathlib import Path
import hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.realtime.relay_metrics import RedisMetrics

def run(output):
    fixtures=[[
        dict(Op='snapshot'),dict(Op='node',Key='node'),dict(Op='connected',Value=1),
        dict(Op='error',Key='write failed'),dict(Op='write',Value=3,Other=77),
        dict(Op='stream',Key='s',Value=3,Other=-1),dict(Op='stream',Key='t',Value=0,Other=-2),
        dict(Op='ttl',Key='legacy',Value=2),dict(Op='ttl',Key='sharded',Value=3),
        dict(Op='ttl',Key='legacy',Value=1),dict(Op='stream',Key='s',Value=8,Other=123),
        dict(Op='retention',Value=2,Other=5),dict(Op='error',Key=''),dict(Op='reset'),
        dict(Op='ttl',Key='legacy',Value=9),dict(Op='reset')]]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_relay_metrics"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/realtime/parity_metrics.go && cd /work && go build -mod=readonly -p=4 -o /out/relay-metrics-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/relay-metrics-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    python=[]
    for steps in fixtures:
        metrics=RedisMetrics();snapshots=[]
        for s in steps:
            op=s['Op'];key=s.get('Key','');value=s.get('Value',0);other=s.get('Other',0)
            if op=='node':metrics.node_id=key
            elif op=='error':metrics.last_error=key
            elif op=='stream':metrics.observe_stream(key,value,other)
            elif op=='ttl':metrics.set_streams_without_ttl(key,value)
            elif op=='write':metrics.xadd_total+=value;metrics.last_xadd_lag_micros=other
            elif op=='retention':metrics.retention_errors+=value;metrics.trimmed+=other
            elif op=='connected':metrics.connected=bool(value)
            elif op=='reset':metrics.reset()
            snapshots.append(metrics.snapshot())
        python.append(snapshots)
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/realtime/metrics.go','server/src/workpal_backend/realtime/relay_metrics.py','server/tests/parity/go_relay_metrics/main.go','server/tests/parity/go_relay_metrics/wrapper.go']
    Path(output).write_text(json.dumps(dict(scope='Original Go Redis metrics snapshot defaults and sixteen state transitions; map replacement, per-mode TTL sums, error overwrite/clear, counters, reset preserves node ID. Does not certify concurrent counter writers or full HTTP metrics/Hub producer coverage.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(scripts=len(fixtures),transitions=sum(map(len,fixtures)),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
