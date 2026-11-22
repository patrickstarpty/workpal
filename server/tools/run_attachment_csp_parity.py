"""Original attachment preview Content-Security-Policy versus Python."""
from pathlib import Path
import base64,hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.files.preview_security import normalize_frame_ancestor,preview_csp

def run(output):
    schemes=['http','https','HTTP','HtTpS','ftp','ws','']
    hosts=['example.com','EXAMPLE.com:443','localhost:5173','[::1]:443','user:pass@example.com','example.com:','example.com:bad','bad host','%41.com','%ff.com','İ.example','*.example.com','[bad]']
    paths=['','/path?q=x#fragment','/%zz','/?q=%zz']
    values=[scheme+'://'+host+path for scheme in schemes for host in hosts for path in paths]
    values.extend(['','*',"'self'",'//example.com','https:opaque',' https://example.com/ '])
    fixtures=[[v] for v in values]+[['https://EXAMPLE.com/path','*','https://example.com',"'none'"]]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_attachment_csp"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/handler/parity_attachment_csp.go && cd /work && go build -mod=readonly -p=4 -o /out/attachment-csp-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/attachment-csp-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    encode=lambda v:base64.b64encode(v.encode('utf8','surrogateescape')).decode()
    python=[dict(sources=[encode(s) if (s:=normalize_frame_ancestor(v)) is not None else None for v in f],csp=encode(preview_csp(f))) for f in fixtures]
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/handler/file.go','server/tests/parity/go_attachment_csp/main.go','server/tests/parity/go_attachment_csp/wrapper.go','server/src/workpal_backend/files/preview_security.py','server/src/workpal_backend/auth/profile_decode.py','server/src/workpal_backend/realtime/origins.py','server/src/workpal_backend/workspaces/decode.py','server/tools/run_attachment_csp_parity.py']
    Path(output).write_text(json.dumps(dict(scope='Original normalizeFrameAncestorSource and attachmentPreviewCSPHeader vs Python, exact bytes and rejection including invalid URL escapes, Unicode, duplicate origins, port/path/scheme. No preview HTTP route or full browser policy enforcement certified.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
