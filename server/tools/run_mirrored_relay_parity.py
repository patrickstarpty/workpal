"""Original Go MirroredRelay lifecycle and synchronous publish outcomes."""
from pathlib import Path
import asyncio,base64,hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.realtime.relay_modes import MirroredRelay
from workpal_backend.realtime.relay_metrics import RedisMetrics

def run(output):
    fixtures=[dict(Scope=scope,ID='id',Exclude='w',EventID='event',Frame=base64.b64encode(b'opaque\xff').decode(),PrimaryError=p,MirrorError=m) for scope in ['workspace','user','global','daemon_runtime','wecom_outbound','unknown'] for p in [False,True] for m in [False,True]]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_mirrored_relay"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/realtime/parity_mirror.go && cd /work && go build -mod=readonly -p=4 -o /out/mirrored-relay-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/mirrored-relay-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    async def observe(f):
        calls=[];lifecycle=[];metrics=RedisMetrics()
        class Child:
            def __init__(self,name,fail):self.node_id=name;self.fail=fail;self.metrics=metrics
            async def start(self,parent):lifecycle.append(['start',self.node_id]);metrics.node_id=self.node_id
            def stop(self):lifecycle.append(['stop',self.node_id])
            async def wait(self):lifecycle.append(['wait',self.node_id])
            def set_daemon_runtime_deliverer(self,value):lifecycle.append(['sink',self.node_id])
            async def publish_with_id(self,scope,identity,exclude,frame,event_id):
                calls.append([self.node_id,scope,identity,exclude,base64.b64encode(frame).decode(),event_id])
                if self.fail:raise RuntimeError(self.node_id+' failed')
        r=MirroredRelay(Child('primary',f['PrimaryError']),Child('mirror',f['MirrorError']))
        await r.start(asyncio.Event());r.set_daemon_runtime_deliverer(None)
        error=''
        try:await r.publish_with_id(f['Scope'],f['ID'],f['Exclude'],base64.b64decode(f['Frame']),f['EventID'])
        except Exception as caught:error=str(caught)
        r.stop();await r.wait()
        return dict(calls=calls,lifecycle=lifecycle,error=error,node_id=r.node_id,metric_node_id=metrics.node_id,metrics=[metrics.mirror_primary_errors,metrics.mirror_secondary_errors,metrics.mirror_divergence_total])
    python=[asyncio.run(observe(f)) for f in fixtures]
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/realtime/relay_lifecycle.go','server/tests/parity/go_mirrored_relay/main.go','server/tests/parity/go_mirrored_relay/wrapper.go','server/src/workpal_backend/realtime/relay_modes.py','server/src/workpal_backend/realtime/relay_metrics.py']
    Path(output).write_text(json.dumps(dict(scope='Original MirroredRelay start/sink/stop/wait ordering and node metric, same-id sequential publish, daemon_runtime primary-only, joined error text and divergence counters. Child boundary recorders, not concurrent cancellation or real Redis IO.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
