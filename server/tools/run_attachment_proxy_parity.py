"""Actual proxyAttachmentDownload against Python with isolated readers."""
from pathlib import Path
import asyncio,hashlib,io,json,sys,subprocess
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.files.proxy import proxy_attachment
class Reader:
    def __init__(self,f):self.f=f;self.raw=io.BytesIO(f['Body'].encode());self.closed=False
    def read(self,n):
        if self.f['Failure']=='read':raise OSError('read failed')
        return self.raw.read(n)
    def close(self):self.closed=True
class Seeker(Reader):
    def seek(self,offset,whence=0):
        if self.f['Failure']=='seek':raise OSError('seek failed')
        return self.raw.seek(offset,whence)
class Storage:
    def __init__(self,f):self.f=f;self.reader=(Seeker if f['Seekable'] else Reader)(f)
    def get_reader(self,key):
        if self.f['Failure']=='open':raise OSError('open failed')
        if self.f['Failure']=='open-cancel':raise asyncio.CancelledError()
        return self.reader
async def evaluate(f):
    messages=[];storage=Storage(f)
    async def send(message):messages.append(message)
    att=dict(content_type=f['ContentType'],filename=f['Filename'],size_bytes=f['Size'])
    await proxy_attachment(att,storage,'key',send,method=f['Method'],request_headers={'range':f['Range']},force_attachment=f['Force'],frame_ancestors=f['Ancestors'],request_error=lambda:asyncio.CancelledError() if f['Cancelled'] else None)
    headers={k.decode():v.decode() for k,v in messages[0]['headers'] if k!=b'content-length'}
    body=b''.join(m.get('body',b'') for m in messages[1:]).decode()
    if headers.get('content-type','').startswith('multipart/byteranges; boundary='):
        boundary=headers['content-type'].split('boundary=')[1];body=body.replace(boundary,'x'*60);headers['content-type']='multipart/byteranges; boundary='+'x'*60
    return dict(status=messages[0]['status'],headers=headers,body=body,closed=storage.reader.closed)

def run(output):
    base=dict(Body='abcdefghij',Method='GET',Range='',ContentType='application/pdf',Filename='report.pdf',Size=10,Seekable=True,Force=False,Cancelled=False,Failure='',Ancestors=['https://app.example/path'])
    fixtures=[dict(base,Seekable=seekable,Range=value,Size=size,Force=force,Method=method)
        for seekable in [False,True] for value in ['', 'bytes=1-3','bytes=0-1,4-5','bytes=99-','invalid'] for size in [-1,3,10] for force in [False,True] for method in ['GET','HEAD']]
    fixtures.extend(dict(base,Seekable=seekable,Cancelled=cancelled,Failure=failure) for seekable in [False,True] for cancelled in [False,True] for failure in ['open','open-cancel','read','seek'])
    fixtures.extend(dict(base,ContentType=media,Filename=filename,Force=force) for media in ['', 'image/png','image/svg+xml','text/plain'] for filename in ['报告.txt','a"b.txt'] for force in [False,True])
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_attachment_proxy"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/handler/parity_attachment_proxy.go && cd /work && go build -mod=readonly -p=4 -o /out/attachment-proxy-oracle ./parity'])
    go=[]
    for offset in range(0,len(fixtures),32):
        result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i','-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0','/out/attachment-proxy-oracle'],input=json.dumps(fixtures[offset:offset+32]))
        go.extend(json.loads(result.stdout))
    python=[asyncio.run(evaluate(f)) for f in fixtures]
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/handler/file.go','server/tests/parity/go_attachment_proxy/main.go','server/tests/parity/go_attachment_proxy/wrapper.go','server/src/workpal_backend/files/proxy.py','server/src/workpal_backend/files/attachment_io.py','server/src/workpal_backend/files/seekable_content.py','server/src/workpal_backend/files/range_stream.py','server/tools/run_attachment_proxy_parity.py']
    Path(output).write_text(json.dumps(dict(scope='Actual proxyAttachmentDownload with isolated seekable/forward readers: status/body/security headers/close, recorded vs actual sizes, Range and pre-open cancellation/errors. Random multipart boundary normalized; Content-Length omitted because recorder/ASGI auto lengths differ on small errors. No live transport or ASGI disconnect certification.',fixtures=fixtures,execution_batch_size=32,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':
    try:raise SystemExit(run(sys.argv[1]))
    except subprocess.CalledProcessError as error:
        print(error.stderr,file=sys.stderr)
        raise
