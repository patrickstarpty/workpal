"""Original Go publishWithID against a recorded Redis command boundary."""
from pathlib import Path
import asyncio,base64,hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.realtime.relay_publisher import RelayPublisher,PublishMetrics
from workpal_backend.realtime.stream_retention import RetentionConfig

def run(output):
    fixtures=[]
    for enabled in [False,True]:
        for failure in ['', 'write', 'expiry']:
            for frame in [b'{"type":"x","actor_id":"a","payload":9007199254740993}',b'opaque\xff']:
                fixtures.append(dict(Scope='user',ID='u',Exclude='w',EventID='e',Frame=base64.b64encode(frame).decode(),Enabled=enabled,MaxLen=7,Failure=failure,Count=2))
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_relay_publish"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/realtime/parity_publish.go && cd /work && go build -mod=readonly -p=4 -o /out/relay-publish-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/relay-publish-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    async def observe(f):
        writes=[];expires=[]
        class Client:
            async def xadd(self,key,values,**options):
                values=dict(values);values['created_at']=b'<clock>'
                writes.append(dict(key=key,values={k:base64.b64encode(v).decode() for k,v in values.items()},**options))
                if f['Failure']=='write':raise OSError('write unavailable')
                return '1-0'
            async def pexpire(self,key,ttl):
                expires.append(dict(key=key,ttl_ns=ttl*1000000))
                if f['Failure']=='expiry':raise OSError('expiry unavailable')
                return True
        metrics=PublishMetrics()
        p=RelayPublisher(Client(),'node',retention=RetentionConfig(max_len=f['MaxLen'],enabled=f['Enabled']),metrics=metrics)
        errors=[]
        for _ in range(f['Count']):
            try:
                await p.publish_with_id(f['Scope'],f['ID'],f['Exclude'],base64.b64decode(f['Frame']),f['EventID'])
                errors.append('')
            except OSError as error:errors.append(str(error))
        return dict(writes=writes,expires=expires,errors=errors,metrics=[metrics.xadd_total,metrics.xadd_errors,metrics.retention_errors])
    python=[asyncio.run(observe(f)) for f in fixtures]
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/realtime/redis_relay.go','server/go/internal/realtime/stream_retention.go',
             'server/tests/parity/go_relay_publish/main.go','server/tests/parity/go_relay_publish/wrapper.go',
             'server/src/workpal_backend/realtime/relay_publisher.py','server/src/workpal_backend/realtime/stream_retention.py',
             'server/src/workpal_backend/realtime/relay_envelope.py']
    Path(output).write_text(json.dumps(dict(scope='Original Go publishWithID command args/bytes, errors, counters and opt-in expiry/retry. Redis command boundary recorder, not actual Go Redis I/O. Clock normalized. No ULID, timeout/cancellation, metrics endpoint, subscription or lifecycle equivalence certified.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},binary_sha256=hashlib.sha256((binaries/'relay-publish-oracle').read_bytes()).hexdigest()),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
