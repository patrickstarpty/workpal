"""Original pinned Go ULID library encoding, with deterministic entropy bytes."""
from pathlib import Path
import hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.realtime.relay_ids import encode_ulid

def run(output):
    fixtures=[dict(MS=ms,Entropy=f'{entropy:020x}') for ms in [0,1,1469918176385,(1<<48)-1,1<<48] for entropy in [0,1,int('D3BFD8D38D18854D03D3',16),(1<<80)-1]]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_relay_ids"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cd /work && go build -mod=readonly -p=4 -o /out/relay-ids-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/relay-ids-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    python=[]
    for f in fixtures:
        try:python.append(encode_ulid(f['MS'],int(f['Entropy'],16)))
        except ValueError as error:python.append(str(error))
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/go.mod','server/go/go.sum','server/tests/parity/go_relay_ids/main.go','server/src/workpal_backend/realtime/relay_ids.py']
    Path(output).write_text(json.dumps(dict(scope='Pinned Go oklog ULID v2.1.2 encoding and time overflow. Deterministic entropy; no PRNG sequence or monotonic-overflow parity certification.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
