"""Original attachment loaders: validation, membership, visibility, query errors."""
from pathlib import Path
import asyncio,hashlib,json,sys,subprocess
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.files.loader import AttachmentLoader,AttachmentLoadError
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
    def row(self):
        return dict(id=parse_uuid(self.f['ID']),workspace_id=parse_uuid(self.f['StoredWorkspace']) if self.f['StoredWorkspace'] else None,issue_id=P if self.f['Bound'] else None,comment_id=None)
    def get_attachment(self,identity,workspace):self.record('scoped',identity,workspace);return self.row()
    def get_attachment_by_id(self,identity):self.record('attachment',identity);return self.row()
    def get_member(self,workspace,user):self.record('member',workspace,user);return {}
    def issue_project(self,identity):self.record('project',identity);return P
    def hidden(self,workspace):
        self.record('hidden',parse_uuid(workspace));hidden=Hidden()
        if self.f['Hidden']:hidden.add([P])
        return hidden

def run(output):
    base=dict(Mode='request',ID=A,Workspace=W,StoredWorkspace=W,User=U,Failure='',Bound=False,Hidden=False,Cancelled=False)
    fixtures=[dict(base,Mode=mode,Bound=bound,Hidden=hidden,Cancelled=cancelled,Failure=failure)
        for mode in ['request','download'] for bound in [False,True] for hidden in [False,True] for cancelled in [False,True]
        for failure in ['', 'scoped','attachment','member','hidden','project','attachment-missing','member-missing','project-missing','hidden-cancel','project-cancel']]
    fixtures.extend(dict(base,Mode=mode,ID=identity,Workspace=workspace,StoredWorkspace=stored,User=user)
        for mode in ['request','download'] for identity in [A,A.upper(),'invalid',''] for workspace in [W,'invalid',''] for stored in [W,''] for user in [U,''])
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_attachment_loader"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/handler/parity_attachment_loader.go && cd /work && go build -mod=readonly -p=4 -o /out/attachment-loader-oracle ./parity'])
    go=[]
    for offset in range(0,len(fixtures),32):
        result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i','-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0','/out/attachment-loader-oracle'],input=json.dumps(fixtures[offset:offset+32]))
        go.extend(json.loads(result.stdout))
    python=[]
    for f in fixtures:
        q=Queries(f);l=AttachmentLoader(q,hidden_projects=q.hidden,request_error=lambda:asyncio.CancelledError() if f['Cancelled'] else None)
        try:
            att=l.for_download(f['ID'],f['User']) if f['Mode']=='download' else l.for_request(f['ID'],f['Workspace'])
            result=dict(ok=True,id=att['id'],status=200,body='',calls=q.calls)
        except AttachmentLoadError as e:
            body='' if e.status==499 else json.dumps({'error':e.message},separators=(',',':'))+'\n'
            result=dict(ok=False,id='',status=e.status,body=body,calls=q.calls)
        python.append(result)
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/handler/file.go','server/go/internal/handler/project_access.go','server/tests/parity/go_attachment_loader/main.go','server/tests/parity/go_attachment_loader/wrapper.go','server/src/workpal_backend/files/loader.py','server/src/workpal_backend/files/access.py','server/src/workpal_backend/auth/membership_cache.py','server/src/workpal_backend/infrastructure/request_cancellation.py','server/tools/run_attachment_loader_parity.py']
    Path(output).write_text(json.dumps(dict(scope='Original loadAttachmentForRequest/Download with generated DB query fixtures, nil membership cache, context member visibility, exact status/body/query order. No full HTTP middleware, live schema, or storage route certification.',fixtures=fixtures,execution_batch_size=32,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':
    try:raise SystemExit(run(sys.argv[1]))
    except subprocess.CalledProcessError as error:
        print(error.stderr,file=sys.stderr)
        raise
