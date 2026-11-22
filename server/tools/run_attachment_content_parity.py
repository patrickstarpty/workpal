"""Original attachment bounded text-preview service versus Python."""
from pathlib import Path
import asyncio,base64,hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.files.reads import AttachmentReads
from workpal_backend.files.loader import AttachmentLoader

def observe(f):
    class Storage:
        opened=closed=position=0
        def key_from_url(self,url):assert url=='object-url';return 'key'
        def get_reader(self,key):
            assert key=='key';self.opened+=1
            if f['Failure']=='open-cancel':raise asyncio.CancelledError()
            if f['Failure']=='open':raise OSError('open failure')
            return self
        def read(self,n):
            if f['Failure']=='read-cancel':raise asyncio.CancelledError()
            if f['Failure']=='read':raise OSError('read failure')
            data=f['Data'].encode();part=data[self.position:self.position+min(n,2)];self.position+=len(part);return part
        def close(self):
            self.closed+=1
            if f['Failure']=='close-cancel':raise asyncio.CancelledError()
            if f['Failure']=='close':raise OSError('close failure')
    store=Storage()
    class Queries:
        def get_attachment(self,identity,workspace):
            assert identity=='11111111-1111-4111-8111-111111111111' and workspace=='22222222-2222-4222-8222-222222222222'
            return dict(id=identity,workspace_id=workspace,issue_id=None,comment_id=None,content_type=f['Mime'],filename=f['Filename'],size_bytes=f['Size'],url='object-url')
    loader=AttachmentLoader(Queries(),hidden_projects=lambda workspace:None)
    service=AttachmentReads(loader,None,store if f['Available'] else None,max_preview_size=f['Limit'],frame_ancestors=f['Ancestors'])
    response=asyncio.run(service.content('11111111-1111-4111-8111-111111111111','22222222-2222-4222-8222-222222222222'))
    return dict(status=response.status_code,headers={key:response.headers.get(key,'') for key in ['Content-Type','Content-Length','X-Original-Content-Type','Cache-Control','X-Content-Type-Options','Content-Security-Policy']},body=base64.b64encode(response.body).decode(),opened=store.opened,closed=store.closed,read=store.position)

def run(output):
    fixtures=[dict(Mime=mime,Filename=name,Size=size,Data=data,Failure=fail,Available=available,Limit=4,Ancestors=['https://WEB.example/path','*','https://web.example']) for mime,name in [('text/html','a.html'),('image/png','a.png'),('image/png','a.py')] for size in [-1,0,4,5] for data in ['', '1234', '12345'] for fail in ['', 'open','read','close','open-cancel','read-cancel','close-cancel'] for available in [False,True]]
    fixtures.extend(dict(Mime='text/plain',Filename='a.txt',Size=3,Data='abc',Failure='',Available=True,Limit=limit,Ancestors=[]) for limit in [-1,0,1,16777217,9223372036854775807])
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_attachment_content"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/handler/parity_attachment_content.go && cd /work && go build -mod=readonly -p=4 -o /out/attachment-content-oracle ./parity'])
    go=[]
    for offset in range(0,len(fixtures),32):
        result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
            '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
            '/out/attachment-content-oracle'],input=json.dumps(fixtures[offset:offset+32]))
        go.extend(json.loads(result.stdout))
    python=[observe(f) for f in fixtures]
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/handler/file.go','server/tests/parity/go_attachment_content/main.go','server/tests/parity/go_attachment_content/wrapper.go','server/src/workpal_backend/files/content.py','server/src/workpal_backend/files/reads.py','server/src/workpal_backend/files/loader.py','server/src/workpal_backend/files/attachment_io.py','server/src/workpal_backend/auth/profile_decode.py','server/src/workpal_backend/files/preview.py','server/src/workpal_backend/files/preview_security.py','server/src/workpal_backend/files/attachment_text_preview.json','server/go/internal/attachmentpreview/size.go','server/tools/run_attachment_content_parity.py']
    Path(output).write_text(json.dumps(dict(scope='Original GetAttachmentContent via chi router with explicit unbound-attachment query fixture versus Python AttachmentReads and AttachmentLoader with strict unbound query fixture: exact response, storage calls, bounded reads and close/error ordering. Database row lookup is fixture-only; bound-project ACL, ASGI route and real storage wiring not certified. Storage cancellation failures follow original 404/502 and ignored-close handling.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
