"""Invoke original Go Client.markSeen, including same-ID concurrent calls."""
from pathlib import Path
import hashlib,json,sys
from concurrent.futures import ThreadPoolExecutor
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.realtime.dedup import SeenEvents

def run(output):
    fixtures=[dict(IDs=ids,Concurrent=False) for ids in [[],['',''],['a','a','b','a'],[str(i) for i in range(128)]+['0','128','0','128'],[str(i) for i in range(513)],['中文',' ','中文','', ' ','😀']]]
    fixtures += [dict(IDs=[identity]*200,Concurrent=True) for identity in ['same','']]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_dedup"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/realtime/parity_dedup.go && cd /work && go build -mod=readonly -p=4 -o /out/dedup-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/dedup-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    python=[]
    for fixture in fixtures:
        seen=SeenEvents()
        if fixture['Concurrent']:
            with ThreadPoolExecutor(max_workers=8) as pool:count=sum(pool.map(seen.mark,fixture['IDs']))
            results=[]
        else:
            results=[seen.mark(identity) for identity in fixture['IDs']];count=sum(results)
        python.append(dict(results=results,first_count=count,window=list(seen._order) or None,size=len(seen._ids)))
    if len(go)!=len(python):raise RuntimeError('missing observations')
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/realtime/hub.go','server/tests/parity/go_dedup/wrapper.go','server/tests/parity/go_dedup/main.go','server/src/workpal_backend/realtime/dedup.py']
    Path(output).write_text(json.dumps(dict(scope='Actual Go Client.markSeen FIFO window, empty bypass, duplicate lifetime and concurrent same-ID first delivery count. Hub routing, slow-client behavior, stream receipts and replay transport not certified.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},binary_sha256=hashlib.sha256((binaries/'dedup-oracle').read_bytes()).hexdigest()),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
