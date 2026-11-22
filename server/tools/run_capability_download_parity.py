"""Original public capability redemption against Python, offline fixtures."""
from pathlib import Path
import asyncio,hashlib,io,json,sys,subprocess
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.files.capability_download import redeem_attachment
from workpal_backend.files.capabilities import AttachmentCapabilities
from workpal_backend.infrastructure.query_errors import NoRows
A='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
SECRET='fixture-attachment-capability-secret-only-32bytes'
CAPS=AttachmentCapabilities(SECRET)
class Queries:
    def __init__(self,f):self.f=f;self.calls=[]
    def get_attachment_by_id(self,identity):
        self.calls.append(['attachment',identity])
        if self.f['Missing']:raise NoRows()
        return dict(id=identity,url='object',filename='image.png',content_type='image/png',size_bytes=3)
class Storage:
    def __init__(self,f):self.f=f;self.calls=[];self.reader=None
    def key_from_url(self,url):self.calls.append(['key',url]);return 'key'
    def get_reader(self,key):
        self.calls.append(['read',key])
        if self.f['OpenFailure']:raise OSError('open failed')
        self.reader=io.BytesIO(b'abc');return self.reader
async def evaluate(f):
    q=Queries(f);storage=Storage(f);messages=[]
    async def send(m):messages.append(m)
    await redeem_attachment(f['ID'],f['Query'].encode(),q,storage if f['Storage'] else None,CAPS,send,frame_ancestors=['https://app.example'])
    return dict(status=messages[0]['status'],headers={k.decode():v.decode() for k,v in messages[0]['headers'] if k!=b'content-length'},body=b''.join(m.get('body',b'') for m in messages[1:]).decode(),calls=storage.calls,db_calls=q.calls,closed=bool(storage.reader and storage.reader.closed))
def run(output):
    fixtures=[]
    for identity in [A,A.upper(),'invalid','']:
        for intent in ['', 'attachment']:
            signature=CAPS.sign(identity,4102444800,intent)
            query='exp=4102444800&sig='+signature+('&dl=1' if intent else '')
            variants=[query,query+'&dl=1','exp=&'+query,query.replace('4102444800','1'),query.replace(signature,'bad'),query+'&sig=bad','sig=bad&'+query,query+'&ignored=%zz',query+'&x=a;b','',query.replace('exp=','exp=+')]
            for raw in variants:
                for missing,storage,failure in [(False,True,False),(True,True,False),(False,False,False),(False,True,True)]:
                    fixtures.append(dict(ID=identity,Query=raw,Missing=missing,Storage=storage,OpenFailure=failure))
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_capability_download"}:/harness:ro','-v',f'{ROOT/"server/tests/parity/go_attachment_loader"}:/loader:ro','-v',f'{ROOT/"server/tests/parity/go_attachment_downloads"}:/downloads:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/handler/parity_capability_download.go && cp /loader/wrapper.go /work/internal/handler/parity_attachment_loader.go && cp /downloads/wrapper.go /work/internal/handler/parity_attachment_downloads.go && cd /work && go build -mod=readonly -p=4 -o /out/capability-download-oracle ./parity'])
    go=[]
    for offset in range(0,len(fixtures),32):
        result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-e','JWT_SECRET='+SECRET,'-i','-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0','/out/capability-download-oracle'],input=json.dumps(fixtures[offset:offset+32]))
        go.extend(json.loads(result.stdout))
    python=[asyncio.run(evaluate(f)) for f in fixtures]
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/handler/attachment_capability.go','server/tests/parity/go_capability_download/main.go','server/tests/parity/go_capability_download/wrapper.go','server/tests/parity/go_attachment_downloads/wrapper.go','server/tests/parity/go_attachment_loader/wrapper.go','server/src/workpal_backend/files/capability_download.py','server/src/workpal_backend/files/capabilities.py','server/src/workpal_backend/files/proxy.py','server/src/workpal_backend/files/attachment_io.py','server/tools/run_capability_download_parity.py']
    Path(output).write_text(json.dumps(dict(scope='Actual DownloadAttachmentWithCapability, offline public test key and expiry 2100 or 1970. Exact logical status/body/security headers and query/storage ordering, generic rejection and download intent, malformed/duplicate query fields. Content-Length transport auto-generation excluded; no live HTTP auth routing certification.',fixtures=fixtures,execution_batch_size=32,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':
    try:raise SystemExit(run(sys.argv[1]))
    except subprocess.CalledProcessError as error:
        print(error.stderr,file=sys.stderr)
        raise
