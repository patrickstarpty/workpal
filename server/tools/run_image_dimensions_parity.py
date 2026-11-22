"""Original Go image metadata dimensions against header-only Python decoder."""
from pathlib import Path
import base64,hashlib,json,sys,struct,subprocess
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
sys.path.insert(0,str(ROOT/'server/tests'))
from workpal_backend.files.image_dimensions import dimensions
from test_image_dimensions import png,png_chunk,jpeg,jpeg_segment,exif

def run(output):
    raw=[b'',b'not image']
    for w,h in [(0,40),(80,40),(100000,50000),(2147483647,2147483647),(2147483648,1),(1,2147483647)]:
        for depth in [0,1,2,4,8,16,32]:
            for color in range(8):
                base=png(w,h,depth,color)
                raw.extend([base,base+png_chunk(b'PLTE',b'\0'*3)+b'\0\0\0\0IDAT'])
    for orientation in range(10):
        for order in ['little','big']:
            base=jpeg();raw.append(base[:2]+jpeg_segment(0xe1,exif(orientation,order))+base[2:])
    for fields in range(256):
        base=b'GIF89a'+struct.pack('<HHBBB',80,40,fields,0,0)
        raw.extend([base,base+b'\0'*768])
    seeds=[png(),png(color=3)+png_chunk(b'PLTE',b'\0'*6)+png_chunk(b'tRNS',b'\0'),jpeg(),jpeg(jfif=False)+b'\xff\xda\0\2',jpeg()[:2]+jpeg_segment(0xe1,exif(6))+jpeg()[2:],b'GIF87a'+struct.pack('<HHBBB',80,40,128,0,0)+b'\0'*6]
    for seed in seeds:
        raw.extend(seed[:cut] for cut in range(len(seed)+1))
        for index in range(len(seed)):
            for byte in [0,1,127,255]:raw.append(seed[:index]+bytes([byte])+seed[index+1:])
    for hv in range(256):
        sof=struct.pack('>BHHB',8,40,80,3)+bytes([1,hv,0,2,0x11,0,3,0x11,0])
        raw.append(b'\xff\xd8'+jpeg_segment(0xe0,b'JFIF\0')+jpeg_segment(0xc0,sof))
    fixtures=[base64.b64encode(v).decode() for v in raw]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_image_dimensions"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cd /work && go build -mod=readonly -p=4 -o /out/image-dimensions-oracle ./parity'])
    go=[]
    for offset in range(0,len(fixtures),32):
        result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
            '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
            '/out/image-dimensions-oracle'],input=json.dumps(fixtures[offset:offset+32]))
        go.extend(json.loads(result.stdout))
    python=[list(size) if (size:=dimensions(value)) is not None else None for value in raw]
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/imagemetadata/dimensions.go','server/tests/parity/go_image_dimensions/main.go','server/src/workpal_backend/files/image_dimensions.py','server/tests/test_image_dimensions.py','server/tools/run_image_dimensions_parity.py']
    stdlib=command(['docker','run','--rm','--network','none','golang:1.26.9','sha256sum','/usr/local/go/src/image/png/reader.go','/usr/local/go/src/image/jpeg/reader.go','/usr/local/go/src/image/gif/reader.go']).stdout
    Path(output).write_text(json.dumps(dict(scope='Original imagemetadata.Dimensions with pinned Go image config readers vs Python: selected PNG/GIF/JPEG headers, invalid/truncated bytes, dimensions, palettes, JPEG sampling and EXIF orientation. No pixel decoding or upload endpoint certification.',fixtures=fixtures,execution_batch_size=32,go=go,python=python,mismatches=mismatches,stdlib_sha256=stdlib,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':
    try:raise SystemExit(run(sys.argv[1]))
    except subprocess.CalledProcessError as error:
        print(error.stderr,file=sys.stderr)
        raise
