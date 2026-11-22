"""Original middleware extractToken versus Python request authentication selection."""
from pathlib import Path
import hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from starlette.requests import Request
from workpal_backend.auth.token_source import extract_token

def run(output):
    authorizations=[[],['Bearer token'],['Bearer '],['bearer ignored'],['Basic ignored'],[' Bearer token'],['Bearer a','Bearer b'],['','Bearer b'],['Basic ignored','Bearer b']]
    cookies=[[],['workpal_auth=first'],['workpal_auth=first; workpal_auth=second'],['workpal_auth=; workpal_auth=second'],['workpal_auth=first','workpal_auth=second'],['workpal_auth="quoted"'],['workpal_auth=bad\\value; workpal_auth=valid'],['workpal_auth= value '],['workpal_auth=ÿ'],['workpal_auth']]
    cookies.extend(['workpal_auth=token;'+'x=1;'*n] for n in [2998,2999,3000])
    fixtures=[dict(Authorization=a,Cookies=c) for a in authorizations for c in cookies]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_token_source"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/middleware/parity_token_source.go && cd /work && go build -mod=readonly -p=4 -o /out/token-source-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/token-source-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    python=[]
    for f in fixtures:
        headers=[(b'authorization',v.encode('utf8')) for v in f['Authorization']]+[(b'cookie',v.encode('utf8')) for v in f['Cookies']]
        token,cookie=extract_token(Request(dict(type='http',headers=headers)))
        python.append(dict(token=token,cookie=cookie))
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/middleware/auth.go','server/tests/parity/go_token_source/main.go','server/tests/parity/go_token_source/wrapper.go','server/src/workpal_backend/auth/token_source.py','server/src/workpal_backend/realtime/request_values.py','server/tools/run_token_source_parity.py']
    Path(output).write_text(json.dumps(dict(scope='Original extractToken vs Python Starlette request selection: first Authorization header, exact Bearer prefix, duplicate/invalid/empty cookies and pinned default Cookie count limit. Does not certify token verification, middleware ordering, CSRF or HTTP wire parsing.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
