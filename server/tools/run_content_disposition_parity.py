"""Original attachment storage Content-Disposition versus Python."""
from pathlib import Path
import base64,hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.files.content_disposition import content_disposition

def run(output):
    names=[b'',b'notes.txt',b'nice"file;.png',b'a\r\nb\\c\x00.txt','中"文.png'.encode(),'emoji-😀.txt'.encode(),b'a\xff.txt',b'\xc0\xaf',b'\xed\xa0\x80']
    names.extend(b'a'+bytes([i])+b'.txt' for i in range(128))
    mimes=['image/png','image/svg+xml',' IMAGE/SVG+XML ; charset=utf-8','IMAGE/PNG; x=y','application/pdf','text/plain','audio/mpeg','video/mp4','','image/','İMAGE/PNG']
    fixtures=[dict(Mime=m,Filename=base64.b64encode(n).decode(),Force=f) for m in mimes for n in names for f in [False,True]]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_content_disposition"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cd /work && go build -mod=readonly -p=4 -o /out/content-disposition-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/content-disposition-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    python=[content_disposition(f['Mime'],base64.b64decode(f['Filename']).decode('utf8','surrogateescape'),force_attachment=f['Force']) for f in fixtures]
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/storage/util.go','server/tests/parity/go_content_disposition/main.go','server/src/workpal_backend/files/content_disposition.py','server/src/workpal_backend/auth/profile_decode.py','server/src/workpal_backend/workspaces/decode.py','server/tools/run_content_disposition_parity.py']
    Path(output).write_text(json.dumps(dict(scope='Original storage.ContentDisposition/AttachmentContentDisposition vs Python: exact header values, all ASCII filename bytes, Unicode, invalid UTF8 replacement, SVG exclusion, MIME normalization and forced-download intent. No download endpoint, presigning or object-storage integration certification.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
