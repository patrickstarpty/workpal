"""Pinned Go stdlib sniffing and handler extension policy versus Python."""
from pathlib import Path
import base64,hashlib,json,random,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.files.mime_sniff import detect_content_type,upload_content_type

def run(output):
    signatures=[b'<!DOCTYPE HTML>',b'<HTML>',b'<HEAD>',b'<SCRIPT>',b'<IFRAME>',b'<H1>',b'<DIV>',b'<FONT>',b'<TABLE>',b'<A>',b'<STYLE>',b'<TITLE>',b'<B>',b'<BODY>',b'<BR>',b'<P>',b'<!-- ',b'<?xml',b'%PDF-',b'%!PS-Adobe-',b'\xfe\xff00',b'\xff\xfe00',b'\xef\xbb\xbf0',b'\x00\x00\x01\x00',b'\x00\x00\x02\x00',b'BM',b'GIF87a',b'GIF89a',b'RIFFxxxxWEBPVP',b'\x89PNG\r\n\x1a\n',b'\xff\xd8\xff',b'FORMxxxxAIFF',b'ID3',b'OggS\x00',b'MThd\x00\x00\x00\x06',b'RIFFxxxxAVI ',b'RIFFxxxxWAVE',b'\x1a\x45\xdf\xa3',b'x'*34+b'LP',b'\x00\x01\x00\x00',b'OTTO',b'ttcf',b'wOFF',b'wOF2',b'\x1f\x8b\x08',b'PK\x03\x04',b'Rar!\x1a\x07\x00',b'Rar!\x1a\x07\x01\x00',b'\x00asm']
    samples=[b'',b'a'*512+b'\0',b'a'*511+b'\0']
    for signature in signatures:
        samples.extend(signature[:n] for n in range(len(signature)+1))
        samples.extend(prefix+signature+suffix for prefix in [b'',b' \t\r\n',b'\x0b'] for suffix in [b'',b'\0binary',b'a'*600])
        samples.extend(signature[:n]+bytes([signature[n]^1])+signature[n+1:] for n in range(len(signature)))
    for size in [0,4,8,12,16,20,24,28,512,516,4294967295]:
        samples.extend(size.to_bytes(4,'big')+b'ftyp'+brands for brands in [b'mp42xxxx',b'isommp42',b'isomxxxxmp42',b'isomxxxxmp42xxxx'])
    samples.extend(b'prefix'+bytes([n])+b'suffix' for n in range(256))
    rng=random.Random(20261122)
    samples.extend(rng.randbytes(n) for n in [1,2,3,4,8,16,36,128,512,513] for _ in range(8))
    fixtures=[dict(Data=base64.b64encode(data).decode(),Filename='file.bin') for data in samples]
    fixtures.extend(dict(Data=base64.b64encode(data).decode(),Filename=name) for data in [b'\0',b'<html>',b'plain',b'\x89PNG\r\n\x1a\n'] for name in ['file.SVG','file.css','file.Js','file.MJS','file.JSON','file.WASM','file.txt','a.json/','x/a.JSON','x.json/a','a.','a.json?x','a.İS','.json'])
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_upload_mime"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/handler/parity_upload_mime.go && cd /work && go build -mod=readonly -p=4 -o /out/upload-mime-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/upload-mime-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    python=[dict(detected=detect_content_type(base64.b64decode(f['Data'])),upload=upload_content_type(base64.b64decode(f['Data']),f['Filename'])) for f in fixtures]
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/handler/file.go','server/tests/parity/go_upload_mime/main.go','server/tests/parity/go_upload_mime/wrapper.go','server/src/workpal_backend/files/mime_sniff.py','server/src/workpal_backend/workspaces/decode.py','server/tools/run_upload_mime_parity.py']
    stdlib=command(['docker','run','--rm','--network','none','golang:1.26.9','sha256sum','/usr/local/go/src/net/http/sniff.go']).stdout.split()[0]
    Path(output).write_text(json.dumps(dict(scope='Pinned Go1.26.9 http.DetectContentType and original handler extContentTypes policy vs Python: signature truncation/mutations, whitespace, MIME precedence, MP4 boxes,512byte boundary, binary/text and extension overrides. No multipart parsing, upload authorization/storage or image dimension certification.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,stdlib_sniff_sha256=stdlib,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
