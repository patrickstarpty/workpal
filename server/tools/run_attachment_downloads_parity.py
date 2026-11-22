"""Original DownloadAttachment dispatch and permission order versus Python."""
from pathlib import Path
import asyncio,hashlib,io,json,sys,subprocess
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.files.downloads import AttachmentDownloads
from workpal_backend.files.loader import AttachmentLoader
from workpal_backend.projects.access import Hidden
from workpal_backend.infrastructure.query_errors import NoRows
A='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
W='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
U='cccccccc-cccc-cccc-cccc-cccccccccccc'
class Queries:
    def __init__(self,f):self.f=f;self.calls=[]
    def record(self,kind,*args):
        self.calls.append([kind,*args])
        if self.f['Failure']==kind:raise RuntimeError('query failed')
        if self.f['Failure']==kind+'-missing':raise NoRows()
    def get_attachment_by_id(self,identity):
        self.record('attachment',identity)
        return dict(id=A,workspace_id=W,issue_id=None,comment_id=None,url=self.f['URL'],filename=self.f['Filename'],content_type=self.f['ContentType'],size_bytes=3)
    def get_member(self,workspace,user):self.record('member',workspace,user);return {}
class Storage:
    def __init__(self,f):self.f=f;self.calls=[];self.reader=None
    def key_from_url(self,url):self.calls.append(['key',url]);return 'key'
    def get_reader(self,key):self.calls.append(['read',key]);self.reader=io.BytesIO(b'abc');return self.reader
class Presigner(Storage):
    def presign_get_with_content_disposition(self,key,ttl,disposition):
        self.calls.append(['presign',key,ttl,disposition])
        if self.f['Failure']=='presign':raise RuntimeError('sign failed')
        if self.f['Failure']=='presign-cancel':raise asyncio.CancelledError()
        return 'https://cdn.example/signed?a=1&b=2'
async def evaluate(f):
    q=Queries(f);loader=AttachmentLoader(q,hidden_projects=lambda w:Hidden())
    storage=(Presigner if f['Store']=='presigner' else Storage)(f)
    service=AttachmentDownloads(loader,None if f['Store']=='none' else storage,mode=f['Mode'],ttl_nanoseconds=f['TTL'],frame_ancestors=['https://app.example/path'])
    messages=[]
    async def send(message):messages.append(message)
    await service.download(A,U,send,method=f['Method'],request_path='/api/attachments/id/download')
    return dict(status=messages[0]['status'],headers={k.decode():v.decode() for k,v in messages[0]['headers'] if k!=b'content-length'},body=b''.join(m.get('body',b'') for m in messages[1:]).decode(),calls=storage.calls,db_calls=q.calls,closed=bool(storage.reader and storage.reader.closed))

def run(output):
    base=dict(Mode='auto',Store='plain',Failure='',URL='https://cdn.example/file',Filename='报告.pdf',ContentType='application/pdf',Method='GET',TTL=0)
    fixtures=[dict(base,Mode=mode,Store=store,URL=url,Method=method) for mode in ['auto','cloudfront','presign','proxy','invalid'] for store in ['none','plain','presigner'] for url in ['http://localhost/file','https://cdn.example/file'] for method in ['GET','HEAD']]
    fixtures.extend(dict(base,Mode=mode,Store=store,Failure=failure,TTL=ttl) for mode in ['auto','presign','proxy'] for store in ['none','presigner'] for failure in ['attachment','attachment-missing','member','member-missing','presign','presign-cancel'] for ttl in [-1,5_500_000_000])
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_attachment_downloads"}:/harness:ro','-v',f'{ROOT/"server/tests/parity/go_attachment_loader"}:/loader:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/handler/parity_attachment_downloads.go && cp /loader/wrapper.go /work/internal/handler/parity_attachment_loader.go && cd /work && go build -mod=readonly -p=4 -o /out/attachment-downloads-oracle ./parity'])
    go=[]
    for offset in range(0,len(fixtures),32):
        result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i','-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0','/out/attachment-downloads-oracle'],input=json.dumps(fixtures[offset:offset+32]))
        go.extend(json.loads(result.stdout))
    python=[asyncio.run(evaluate(f)) for f in fixtures]
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/handler/file.go','server/tests/parity/go_attachment_downloads/main.go','server/tests/parity/go_attachment_downloads/wrapper.go','server/tests/parity/go_attachment_loader/wrapper.go','server/src/workpal_backend/files/downloads.py','server/src/workpal_backend/files/loader.py','server/src/workpal_backend/files/proxy.py','server/src/workpal_backend/files/attachment_io.py','server/src/workpal_backend/files/redirect.py','server/tools/run_attachment_downloads_parity.py']
    Path(output).write_text(json.dumps(dict(scope='Actual DownloadAttachment with original generated query row fixtures and isolated storage. Permission/query order, mode selection, missing CloudFront, presign parameters/failure, proxy body and close. Successful CloudFront signing tested separately. Content-Length transport auto-generation excluded; no middleware/schema/live route certification.',fixtures=fixtures,execution_batch_size=32,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':
    try:raise SystemExit(run(sys.argv[1]))
    except subprocess.CalledProcessError as error:
        print(error.stderr,file=sys.stderr)
        raise
