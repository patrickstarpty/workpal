"""Pinned Go http.Redirect download response parity."""
from pathlib import Path
import hashlib,json,sys,subprocess
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.files.redirect import download_redirect

def run(output):
    targets=['https://cdn.example/a?x=1&y=2','https://cdn.example/文件','../a','../../../../a','/a//b/../c/','//cdn.example/a','///a//b','?q=1','#fragment','','.','..','./','/','/a/..','/a/%2f/../b','/bad%escape/../x','/a?bad=%xx','/a#bad%xx','https://user:pass@cdn.example/a','https://cdn.example/a?x="<&\'','http://[::1]/a','https://[bad]/x','data:text/plain,a','http:a/../b','1:bad','/a\\b/../c','/a/../c#x/../y','/a/../c?x/../y','//user@/a/../b']
    fixtures=[dict(Target=target,Path=path,Method=method,ContentType=ct) for target in targets for path in ['/api/attachments/id','/a%2Fb/id','/'] for method in ['GET','HEAD','POST'] for ct in ['', 'custom']]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_download_redirect"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cd /work && go build -mod=readonly -p=4 -o /out/download-redirect-oracle ./parity'])
    go=[]
    for offset in range(0,len(fixtures),32):
        result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i','-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0','/out/download-redirect-oracle'],input=json.dumps(fixtures[offset:offset+32]))
        go.extend(json.loads(result.stdout))
    python=[]
    for f in fixtures:
        r=download_redirect(f['Target'],request_path=f['Path'],method=f['Method'],headers={'content-type':f['ContentType']} if f['ContentType'] else {})
        python.append(dict(status=r.status_code,body=r.body.decode(),location=r.headers['location'],content_type=r.headers.get('content-type','')))
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/tests/parity/go_download_redirect/main.go','server/src/workpal_backend/files/redirect.py','server/src/workpal_backend/realtime/origins.py','server/tools/run_download_redirect_parity.py']
    stdlib=command(['docker','run','--rm','--network','none','golang:1.26.9','sha256sum','/usr/local/go/src/net/http/server.go']).stdout.strip()
    Path(output).write_text(json.dumps(dict(scope='Pinned Go http.Redirect 302 exact body, Location and Content-Type, absolute/relative/invalid URLs and request method. Recorder semantics; excludes net/http transport header serialization.',fixtures=fixtures,execution_batch_size=32,go=go,python=python,mismatches=mismatches,stdlib_sha256=stdlib,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':
    try:raise SystemExit(run(sys.argv[1]))
    except subprocess.CalledProcessError as error:
        print(error.stderr,file=sys.stderr)
        raise
