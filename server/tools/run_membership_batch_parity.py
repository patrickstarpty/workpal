"""Original Go checkWriteMembership fixed-cohort decisions."""
from pathlib import Path
import asyncio,hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.realtime.membership_batch import MembershipBatcher,_Request

def run(output):
    fixtures=[]
    for states in [[],['live'],['live','live','live'],['expired','live','cancelled'],['expired','cancelled']]:
        for mode in ['allow','deny','error','missing']:
            for cancel in [False,True]:
                fixtures.append(dict(IDs=[['w','u'] if i<2 else ['x','v'] for i in range(len(states))],States=states,Mode=mode,CancelDuring=cancel))
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_membership_batch"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/realtime/parity_membership.go && cd /work && go build -mod=readonly -p=4 -o /out/membership-batch-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/membership-batch-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    async def observe(f):
        loop=asyncio.get_running_loop();requests=[];calls=[]
        for identity,state in zip(f['IDs'],f['States']):
            future=loop.create_future()
            if state=='cancelled':future.cancel()
            requests.append(_Request(tuple(identity),future,loop.time()+(-1 if state=='expired' else 60)))
        async def lookup(ids):
            if f['Mode']=='missing':raise RuntimeError('membership checker unavailable')
            calls.append([list(i) for i in ids])
            if f['CancelDuring'] and requests:requests[0].result.cancel()
            if f['Mode']=='error':raise OSError('query unavailable')
            return {identity:True for identity in ids} if f['Mode']=='allow' else {}
        batcher=MembershipBatcher(lookup)
        await batcher._check(requests)
        return dict(results=[False if r.result.cancelled() else r.result.result() for r in requests],calls=calls)
    python=[asyncio.run(observe(f)) for f in fixtures]
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/realtime/membership_batch.go','server/tests/parity/go_membership_batch/main.go',
             'server/tests/parity/go_membership_batch/wrapper.go','server/src/workpal_backend/realtime/membership_batch.py']
    Path(output).write_text(json.dumps(dict(scope='Original Go checkWriteMembership fixed-cohort query dedup/order and decisions for live/expired/cancelled/error/missing/denied cases. Cancellation maps to false, including cancelled Python futures. No exact timing/collector scheduling, SQL query equivalence, worker cancellation or transport certification.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},binary_sha256=hashlib.sha256((binaries/'membership-batch-oracle').read_bytes()).hexdigest()),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
