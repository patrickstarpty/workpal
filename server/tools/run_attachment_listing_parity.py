"""Original issue loader: identifier resolution, visibility and query errors."""
from pathlib import Path
import asyncio,hashlib,json,sys,subprocess
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.issues.loader import IssueLoader
from workpal_backend.files.inventory import AttachmentInventory,AttachmentListing
from workpal_backend.files.metadata import AttachmentMetadata
from workpal_backend.projects.access import Hidden
from workpal_backend.infrastructure.query_errors import NoRows
from workpal_backend.infrastructure.go_uuid import parse_uuid
A='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
W='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
U='cccccccc-cccc-cccc-cccc-cccccccccccc'
P='dddddddd-dddd-dddd-dddd-dddddddddddd'
class Queries:
    def __init__(self,f):self.f=f;self.calls=[]
    def record(self,kind,*args):
        self.calls.append([kind,*args])
        failure=self.f['Failure']
        if failure==kind:raise RuntimeError('query failed')
        if failure==kind+'-missing':raise NoRows()
        if failure==kind+'-cancel':raise asyncio.CancelledError()
    def row(self):return dict(id=A,workspace_id=parse_uuid(self.f['Workspace']),project_id=P if self.f['Bound'] else None)
    def get_workspace(self,identity):self.record('workspace',identity);return dict(name=self.f['Name'],issue_prefix=self.f['Prefix'])
    def get_issue_in_workspace(self,identity,workspace):self.record('issue',identity,workspace);return self.row()
    def get_issue_by_number(self,workspace,number):self.record('number',workspace,number);return self.row()
    def list_attachments_by_issue(self,identity,workspace):
        self.record('attachments',identity,workspace)
        return [dict(id=P,workspace_id=workspace,issue_id=A,comment_id=parse_uuid(c) if c else None,uploader_type='member',uploader_id=None,filename='file.txt',url='https://storage/object',content_type='text/plain',size_bytes=3,created_at=None) for c in self.f['Comments']]
    def list_comment_origins_for_issue(self,ids,identity,workspace):
        self.record('origins',ids,identity,workspace)
        return [dict(id=parse_uuid(o['ID']),author_type=o['AuthorType'],author_id=parse_uuid(o['AuthorID']) if o['AuthorID'] else None,created_at='2026-11-22T12:00:00Z' if o['Time'] else None) for o in self.f['Origins']]
    def hidden(self,workspace):
        self.record('hidden',parse_uuid(workspace));hidden=Hidden()
        if self.f['Hidden']:hidden.add([P])
        return hidden

def run(output):
    base=dict(ID=A,Workspace=W,User=U,Failure='',Prefix='ABC',Name='A2b-c world',Bound=False,Hidden=False,Cancelled=False,Stable=False,Comments=[U,U,'',P],Origins=[dict(ID=U,AuthorType='member',AuthorID=U,Time=True)])
    fixtures=[dict(base,Comments=comments,Failure=failure,Stable=stable) for comments in [[],[''],[U],[U,U,'',P]] for stable in [False,True] for failure in ['', 'attachments','attachments-cancel','origins','origins-cancel']]
    fixtures.extend(dict(base,Origins=origins) for origins in [[],[dict(ID=U,AuthorType='agent',AuthorID='',Time=False)],[dict(ID=U,AuthorType='member',AuthorID=U,Time=True),dict(ID=U,AuthorType='agent',AuthorID=P,Time=False)],[dict(ID=P,AuthorType='',AuthorID='',Time=False)]])
    fixtures.extend(dict(base,ID=identity,Bound=bound,Hidden=hidden,Cancelled=cancelled,Failure=failure) for identity in [A,'abc-42','invalid'] for bound,hidden in [(False,False),(True,False),(True,True)] for cancelled in [False,True] for failure in ['', 'issue-cancel','hidden-cancel'])
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_attachment_listing"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/handler/parity_attachment_listing.go && cd /work && go build -mod=readonly -p=4 -o /out/attachment-listing-oracle ./parity'])
    go=[]
    for offset in range(0,len(fixtures),32):
        result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i','-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0','/out/attachment-listing-oracle'],input=json.dumps(fixtures[offset:offset+32]))
        go.extend(json.loads(result.stdout))
    python=[]
    for f in fixtures:
        q=Queries(f);loader=IssueLoader(q,hidden_projects=q.hidden,request_error=lambda:asyncio.CancelledError() if f['Cancelled'] else None)
        service=AttachmentListing(loader,AttachmentInventory(q,AttachmentMetadata(None)))
        response=asyncio.run(service.list(f['ID'],f['User'],f['Workspace'],stable=f['Stable']))
        python.append(dict(status=response.status_code,body=json.loads(response.body) if response.body else None,raw_body=response.body.decode(),calls=q.calls))
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/handler/handler.go','server/go/internal/handler/workspace.go','server/go/internal/handler/project_access.go','server/tests/parity/go_attachment_listing/main.go','server/tests/parity/go_attachment_listing/wrapper.go','server/src/workpal_backend/issues/loader.py','server/src/workpal_backend/realtime/origins.py','server/src/workpal_backend/infrastructure/request_cancellation.py','server/tools/run_attachment_listing_parity.py','server/go/internal/handler/file.go','server/src/workpal_backend/files/inventory.py','server/src/workpal_backend/files/metadata.py','server/src/workpal_backend/infrastructure/go_time.py']
    Path(output).write_text(json.dumps(dict(scope='Original ListAttachments exact JSON response bytes and handler with strict issue/attachment/origin query fixtures, scoped authorization, origin deduplication, missing/duplicate origins, metadata and cancellation/error order. No live middleware, canonical schema or physical DB isolation certification.',fixtures=fixtures,execution_batch_size=32,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':
    try:raise SystemExit(run(sys.argv[1]))
    except subprocess.CalledProcessError as error:
        print(error.stderr,file=sys.stderr)
        raise
