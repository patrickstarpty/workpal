"""Pinned Go attachment ServeContent path versus asynchronous Python stream."""
from pathlib import Path
import asyncio,hashlib,io,json,sys,subprocess
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.files.seekable_content import serve_seekable_attachment
class Reader:
    def __init__(self,body):self.file=io.BytesIO(body.encode())
    async def read(self,n):return self.file.read(n)
    async def seek(self,offset,whence=0):return self.file.seek(offset,whence)
async def evaluate(f):
    messages=[]
    async def send(m):messages.append(m)
    await serve_seekable_attachment(Reader(f['Body']),send,method=f['Method'],request_headers=f['Headers'],headers={b'content-type':b'text/plain',b'cache-control':b'no-store',b'content-disposition':b'attachment'})
    headers={k.decode():v.decode() for k,v in messages[0]['headers']}
    body=b''.join(m.get('body',b'') for m in messages[1:]).decode()
    if headers.get('content-type','').startswith('multipart/byteranges; boundary='):
        boundary=headers['content-type'].split('boundary=')[1];body=body.replace(boundary,'x'*60);headers['content-type']='multipart/byteranges; boundary='+'x'*60
    return dict(status=messages[0]['status'],body=body,headers=headers)

def run(output):
    ranges=['','bytes=','bytes=,','bytes=0-1','bytes=2-4','bytes=99-100','bytes=99-invalid','bytes=-0','bytes=-1','bytes=-999','bytes=0-','bytes=5-2','bytes=0-1,4-5','bytes=0-9,0-9','bytes=99-,0-1','bytes=-0,0-1','bytes= 0 - 1 ','bytes=+0-+1','bytes=0--1','bytes=0-9223372036854775808','bytes=9223372036854775808-','items=0-1','Bytes=0-1',' bytes=0-1','bytes=0-1\n','bytes=\u00a00-1','bytes='+','.join(['0-0']*200),'bytes='+','.join(['invalid']*201)]
    fixtures=[dict(Body=body,Method=method,Headers={'range':value}) for body in ['','a','abcdefghij'] for method in ['GET','HEAD','POST'] for value in ranges]
    tags=['\r*\n','\v*\f','','*',' *garbage',',,*','"other"','W/"other"','"other",*','"other"*','invalid,*','"bad space",*','\t*\t']
    fixtures.extend(dict(Body='abcdefghij',Method=method,Headers={'range':'bytes=0-1',header:value}) for method in ['GET','HEAD','POST'] for header in ['if-match','if-none-match','if-range','if-modified-since','if-unmodified-since'] for value in tags)
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_seekable_content"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cd /work && go build -mod=readonly -p=4 -o /out/seekable-content-oracle ./parity'])
    go=[]
    for offset in range(0,len(fixtures),32):
        result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i','-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0','/out/seekable-content-oracle'],input=json.dumps(fixtures[offset:offset+32]))
        go.extend(json.loads(result.stdout))
    python=[asyncio.run(evaluate(f)) for f in fixtures]
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/tests/parity/go_seekable_content/main.go','server/src/workpal_backend/files/seekable_content.py','server/src/workpal_backend/files/ranges.py','server/tools/run_seekable_content_parity.py']
    stdlib=command(['docker','run','--rm','--network','none','golang:1.26.9','sha256sum','/usr/local/go/src/net/http/fs.go']).stdout.strip()
    Path(output).write_text(json.dumps(dict(scope='Go ServeContent with attachment caller explicit content type, zero modification time, no ETag, bytes.Reader. Exact status/headers/body; random multipart boundary normalized to 60 x bytes. No storage failure/transport backpressure/cancellation certification.',fixtures=fixtures,execution_batch_size=32,go=go,python=python,mismatches=mismatches,stdlib_sha256=stdlib,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':
    try:raise SystemExit(run(sys.argv[1]))
    except subprocess.CalledProcessError as error:
        print(error.stderr,file=sys.stderr)
        raise
