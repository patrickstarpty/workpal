"""Original attachment forward-only byte-range parser versus Python."""
from pathlib import Path
import hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.files.ranges import parse_single_byte_range

def run(output):
    parts=['','0','1','9','10','100','+1','-1','+0','-0','01','x','１','9223372036854775807','9223372036854775808','-9223372036854775808','0'*5000+'1']
    headers=['bytes='+a+'-'+b for a in parts for b in parts]
    headers.extend(['','bytes=','Bytes=0-1','items=0-1','bytes=garbage,garbage','bytes=0-1,','bytes=0','bytes=\u00851\u00a0-\u20039','bytes=\x1c1-9',' bytes=0-1'])
    fixtures=[dict(Header=h,Size=s) for h in headers for s in [0,1,10,9223372036854775807]]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_attachment_ranges"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/handler/parity_attachment_ranges.go && cd /work && go build -mod=readonly -p=4 -o /out/attachment-ranges-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/attachment-ranges-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    python=[list(parse_single_byte_range(f['Header'],f['Size'])) for f in fixtures]
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/handler/file.go','server/tests/parity/go_attachment_ranges/main.go','server/tests/parity/go_attachment_ranges/wrapper.go','server/src/workpal_backend/files/ranges.py','server/src/workpal_backend/auth/profile_decode.py','server/tools/run_attachment_ranges_parity.py']
    Path(output).write_text(json.dumps(dict(scope='Original parseSingleByteRange vs Python parser, including signed int64 numeric boundaries, long zero prefixes, Unicode whitespace, empty files and unsupported multi-range. No HTTP response streaming, seekable multipart, authorization or attachment endpoint certification.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
