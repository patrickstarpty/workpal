"""Pinned Go MIME parameter parser versus Python, preserving raw value bytes."""
from pathlib import Path
import base64,hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.files.mime_parameters import parse_media_type

def run(output):
    bases=['','text','text/plain','TEXT/PLAIN',' text/plain ','text /plain','text/','text/plain/extra','form-data','α/β']
    parameters=['',';',';;','; x=a','; X=a; x=a','; x=a; x=b','; x=""','; x=','; x="unterminated','; x="line\r\n"','; filename="C:\\dir\\file.txt"','; filename="a\\\"b.txt"',"; filename=plain; filename*=utf-8''%E4%B8%AD.txt","; filename=plain; filename*=other''ignored","; filename*0*=utf-8''%E4; filename*1*=%B8%AD","; x*0*=bad''discard; x*1=tail","; x*0=a; x*0*=utf-8''b; x*1=c","; x*1=missing","; x*=utf-8''%zz","; x*0*=utf-8''start; x*1*=%zz; x*2=end",';\u0085x=\u00a0a','; x="a\x00b"']
    raw=[(base+param).encode() for base in bases for param in parameters]
    raw.extend(b'form-data; filename="a'+bytes([n])+b'b"' for n in range(256))
    raw.extend(b'form-data; filename*=utf-8\'\'%'+f'{n:02X}'.encode() for n in range(256))
    fixtures=[base64.b64encode(value).decode() for value in raw]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_mime_parameters"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cd /work && go build -mod=readonly -p=4 -o /out/mime-parameters-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/mime-parameters-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    python=[]
    for f in fixtures:
        media,params,error=parse_media_type(base64.b64decode(f).decode('utf8','surrogateescape'))
        python.append(dict(media=media,params=None if params is None else {k:base64.b64encode(v.encode('utf8','surrogateescape')).decode() for k,v in params.items()},error=error or ''))
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/tests/parity/go_mime_parameters/main.go','server/src/workpal_backend/files/mime_parameters.py','server/src/workpal_backend/auth/profile_decode.py','server/src/workpal_backend/workspaces/decode.py','server/tools/run_mime_parameters_parity.py']
    stdlib=command(['docker','run','--rm','--network','none','golang:1.26.9','sha256sum','/usr/local/go/src/mime/mediatype.go']).stdout.split()[0]
    Path(output).write_text(json.dumps(dict(scope='Pinned Go1.26.9 mime.ParseMediaType vs Python: exact parsed media, raw parameter bytes, nil-vs-empty map and error strings; quoted values, duplicate names, RFC2231 and invalid bytes. No multipart boundary/header parser or upload endpoint certification.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,stdlib_sha256=stdlib,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
