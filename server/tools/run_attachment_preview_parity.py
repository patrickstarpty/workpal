"""Original attachment text-preview whitelist versus Python."""
from pathlib import Path
import hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.files.preview import is_text_previewable

def run(output):
    rules=json.loads((ROOT/'server/go/internal/handler/attachment_text_preview.json').read_text())
    names=['file.'+ext for ext in rules['extensions']]+rules['basenames']+['a.PY','C:\\folder\\Dockerfile','dir/.env/','dir/../Makefile','test.İNİ','test.py ','x.pdf','x.png','file.bin','','/','.', '..','folder/..','file.PY/..']
    mimes=['','image/png','application/octet-stream','TEXT/PLAIN',' TEXT/PLAIN ; charset=utf-8','application/jsonx','application/pdf','text/','text']+rules['content_types']
    fixtures=[dict(Mime=m,Filename=n) for m in mimes for n in names]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_attachment_preview"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/handler/parity_attachment_preview.go && cd /work && go build -mod=readonly -p=4 -o /out/attachment-preview-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/attachment-preview-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    python=[is_text_previewable(f['Mime'],f['Filename']) for f in fixtures]
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/handler/file.go','server/tests/parity/go_attachment_preview/main.go','server/tests/parity/go_attachment_preview/wrapper.go','server/src/workpal_backend/files/preview.py','server/src/workpal_backend/auth/profile_decode.py','server/src/workpal_backend/workspaces/decode.py','server/go/internal/handler/attachment_text_preview.go','server/go/internal/handler/attachment_text_preview.json','server/src/workpal_backend/files/attachment_text_preview.json','server/tools/run_attachment_preview_parity.py']
    Path(output).write_text(json.dumps(dict(scope='Original isTextPreviewable vs Python whitelist selection using packaged identical rules, MIME parameters, filename paths and Unicode simple lowercase. No content endpoint, size limit, security headers or authorization certification.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
