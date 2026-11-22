"""Pinned google/uuid v1.6.0 NewV7FromReader with injected time and entropy."""
from pathlib import Path
import base64,hashlib,json,sys,subprocess
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.infrastructure.uuid7 import UUID7Generator

def evaluate(f):
    calls=0
    clock=0
    def now():
        nonlocal calls
        calls+=1
        return clock
    generator=UUID7Generator(clock_ns=now,random_bytes=lambda n:base64.b64decode(f['Random']))
    values=[];failed=[]
    for clock in f['Nanos']:
        try:values.append(generator());failed.append(False)
        except OSError:values.append('');failed.append(True)
    return dict(values=values,failed=failed,clock_calls=calls)

def run(output):
    sequences=[[0,0,0],[-1,-999999,-1000000,0,1],[1234567890,1234567890,1234000000,1235000000],[(1<<63)-1,(1<<63)-2,-(1<<63)],[0]*4098,[999999]*200]
    fixtures=[dict(Nanos=nanos,Random=base64.b64encode(random).decode()) for nanos in sequences for random in [bytes(range(16)),b'\xff'*16,b'',b'a'*15]]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_uuid7"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod:ro','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp -a /go/pkg/mod/github.com/google/uuid@v1.6.0 /work/uuid && chmod -R u+w /work/uuid && cp /harness/wrapper.go /work/uuid/parity_v7.go && cp /harness/main.go /work/parity/main.go && cd /work && go mod edit -replace=github.com/google/uuid=/work/uuid && go build -mod=readonly -p=4 -o /out/uuid7-oracle ./parity'])
    go=[]
    for f in fixtures:
        result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i','-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0','/out/uuid7-oracle'],input=json.dumps([f]))
        go.extend(json.loads(result.stdout))
    python=[evaluate(f) for f in fixtures]
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    dependency=command(['docker','run','--rm','--network','none','-v','workpal-go-parity-modcache:/go/pkg/mod:ro','golang:1.26.9','sha256sum','/go/pkg/mod/github.com/google/uuid@v1.6.0/version7.go','/go/pkg/mod/github.com/google/uuid@v1.6.0/version4.go','/go/pkg/mod/github.com/google/uuid@v1.6.0/time.go']).stdout.strip()
    sources=['server/tests/parity/go_uuid7/main.go','server/tests/parity/go_uuid7/wrapper.go','server/src/workpal_backend/infrastructure/uuid7.py','server/tools/run_uuid7_parity.py']
    Path(output).write_text(json.dumps(dict(scope='Actual google/uuid v1.6.0 NewV7FromReader with additive helper in disposable module copy; unmodified library implementation, injected timeNow/entropy, reset lastV7time per fixture. Work-only module replacement; original/cache read-only. Sequential monotonicity, int64 epochs, carry and entropy failures; no cross-process/concurrency ordering claim.',fixtures=fixtures,execution_batch_size=1,go=go,python=python,mismatches=mismatches,dependency_sha256=dependency,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),generated=sum(len(f['Nanos']) for f in fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':
    try:raise SystemExit(run(sys.argv[1]))
    except subprocess.CalledProcessError as error:
        print(error.stderr,file=sys.stderr)
        raise
