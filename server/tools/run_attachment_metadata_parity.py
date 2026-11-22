"""Original attachmentToResponse field and durable URL projection."""
from pathlib import Path
from datetime import datetime,timezone,timedelta
import hashlib,json,sys,subprocess
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.files.metadata import AttachmentMetadata
A='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
W='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
class Storage:
    def __init__(self,f):self.is_local=f['Store']=='local';self.f=f
    def cdn_domain(self):return self.f['CDN']
def evaluate(f):
    a=dict(id=A,workspace_id=W,uploader_type='member',uploader_id=None,filename='报告.pdf',url=f['URL'],content_type='application/pdf',size_bytes=3,width=f['Width'],height=f['Height'],created_at=None if f['ZeroTime'] else datetime(2026,11,22,12,30,45,999999,tzinfo=timezone(timedelta(seconds=f['Offset']))))
    if f['Bound']:a[f['Bound']]=W
    service=AttachmentMetadata(None if f['Store']=='none' else Storage(f),object() if f['Signed'] else None,public_url=f['PublicURL'])
    return service.response(a,stable=f['Stable'])
def run(output):
    base=dict(Store='none',CDN='',PublicURL='',URL='https://cdn.example/file',Bound='',Stable=False,Signed=False,ZeroTime=False,Offset=28800,Width=None,Height=None)
    fixtures=[dict(base,Store=store,CDN=cdn,PublicURL=public,Bound=bound,Stable=stable,Signed=signed) for store,cdn in [('none',''),('local',''),('remote',''),('remote','cdn.example')] for public in ['', 'https://api.example///'] for bound in ['', 'issue_id','comment_id','chat_session_id','chat_message_id','task_id','source_context_id'] for stable,signed in [(False,False),(True,False),(True,True)]]
    fixtures.extend(dict(base,Store='remote',CDN='cdn.example',Width=width,Height=height,Offset=offset,ZeroTime=zero,URL=url) for width,height in [(None,None),(0,0),(10,None),(None,20),(-1,20),(2147483647,1)] for offset in [0,28800,-19800,29,-29] for zero in [False,True] for url in ['https://cdn.example/file','/uploads/file','https://cdn.example/file?Signature=x'])
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_attachment_metadata"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/handler/parity_attachment_metadata.go && cd /work && go build -mod=readonly -p=4 -o /out/attachment-metadata-oracle ./parity'])
    go=[]
    for offset in range(0,len(fixtures),32):
        result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i','-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0','/out/attachment-metadata-oracle'],input=json.dumps(fixtures[offset:offset+32]))
        go.extend(json.loads(result.stdout))
    python=[evaluate(f) for f in fixtures]
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/handler/file.go','server/go/internal/handler/avatar.go','server/tests/parity/go_attachment_metadata/main.go','server/tests/parity/go_attachment_metadata/wrapper.go','server/src/workpal_backend/files/metadata.py','server/src/workpal_backend/files/attachment_urls.py','server/src/workpal_backend/infrastructure/go_time.py','server/tools/run_attachment_metadata_parity.py']
    Path(output).write_text(json.dumps(dict(scope='Original attachmentToResponse JSON field projection, nullable dimensions/parents, bound local URLs, durable URLs, fixed-offset/zero timestamps, stable-mode signer avoidance. Successful CF signatures separately certified; signed_response dispatch not included.',fixtures=fixtures,execution_batch_size=32,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':
    try:raise SystemExit(run(sys.argv[1]))
    except subprocess.CalledProcessError as error:
        print(error.stderr,file=sys.stderr)
        raise
