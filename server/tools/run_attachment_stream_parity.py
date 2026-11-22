"""Original attachment forward-only streaming responses versus Python."""
from pathlib import Path
import asyncio,base64,hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.files.range_stream import serve_proxy_range

async def observe(f):
    data=f['Data'].encode();messages=[];writes=0
    class Reader:
        position=0
        async def read(self,n):
            if f['FailAt']>=0 and self.position>=f['FailAt']:raise OSError('fixture read failure')
            part=data[self.position:self.position+min(n,2)];self.position+=len(part);return part
    reader=Reader()
    async def send(message):
        nonlocal writes
        if message.get('body'):
            writes+=1
            if f.get('WriteFail'):raise BrokenPipeError('fixture write failure')
        messages.append(message)
    await serve_proxy_range(reader,f['Size'],f['Header'],send,headers=[(b'content-type',b'application/octet-stream')])
    start=messages[0];headers=dict(start['headers'])
    return dict(status=start['status'],headers={key:headers.get(key.lower().encode(),b'').decode() for key in ['Accept-Ranges','Content-Range','Content-Length','Content-Type']},body=base64.b64encode(b''.join(m.get('body',b'') for m in messages)).decode(),read=reader.position,writes=writes)

def run(output):
    headers=['','bytes=0-1','bytes=2-4','bytes=2-','bytes=-3','bytes=20-','bytes=0-1,4-5','items=0-1','bytes=0-invalid',' bytes=0-1 ']
    fixtures=[dict(Header=h,Size=size,Data=data,FailAt=fail) for h in headers for size in [-1,0,3,10] for data in ['', '012','0123456789'] for fail in [-1,0,2,6]]
    fixtures.extend(dict(Header=h,Size=10,Data='0123456789',FailAt=-1,WriteFail=True) for h in ['', 'bytes=2-4','bytes=-3','bytes=0-1,4-5'])
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_attachment_stream"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/handler/parity_attachment_stream.go && cd /work && go build -mod=readonly -p=4 -o /out/attachment-stream-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/attachment-stream-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    python=[asyncio.run(observe(f)) for f in fixtures]
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/handler/file.go','server/tests/parity/go_attachment_stream/main.go','server/tests/parity/go_attachment_stream/wrapper.go','server/src/workpal_backend/files/ranges.py','server/src/workpal_backend/files/range_stream.py','server/src/workpal_backend/auth/profile_decode.py','server/tools/run_attachment_stream_parity.py']
    Path(output).write_text(json.dumps(dict(scope='Original serveProxyRange httptest recorder vs Python ASGI send: exact status, semantic headers, concatenated bytes and reader progress, including size mismatch, early/late injected read errors and body-write failure attempts, empty/unknown size and multi-range fallback. Chunk-boundary transport, real sockets, cancellation, seekable multipart and endpoint authorization not certified.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
