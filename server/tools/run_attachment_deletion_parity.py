"""Original DeleteAttachment handler through generated DB row and transaction fixtures."""
from pathlib import Path
import hashlib,json,sys,subprocess
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
import asyncio
from workpal_backend.files.write_transactions import AttachmentWriter
from workpal_backend.files.loader import AttachmentLoader
from workpal_backend.files.mutations import AttachmentMutations
from workpal_backend.files.events import AttachmentEvents
from workpal_backend.comments.groups import CommentGroups
from workpal_backend.comments.projection import comment_response
from workpal_backend.projects.access import Hidden
from workpal_backend.infrastructure.query_errors import NoRows
from workpal_backend.infrastructure.go_uuid import parse_uuid
A='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';W='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
I='cccccccc-cccc-cccc-cccc-cccccccccccc';U='dddddddd-dddd-dddd-dddd-dddddddddddd'
class Queries:
    def __init__(self,f):self.f=f;self.calls=[];self.transaction=False
    def record(self,kind,*args):
        self.calls.append([kind,*args]);failure=self.f['Failure']
        if failure==kind:raise RuntimeError(kind+' failed')
        if failure==kind+'-missing':raise NoRows()
        if failure==kind+'-cancel':raise asyncio.CancelledError()
    def begin(self):self.record('begin');self.transaction=True;return self
    def execute(self,sql,args):self.record('execute',sql,*args)
    def commit(self):self.record('commit')
    def rollback(self):self.record('rollback')
    def lock_issue_for_attachment_write(self,*args):self.record('issue',*args)
    def row(self):
        f=self.f
        return dict(id=parse_uuid(f['ID']),workspace_id=parse_uuid(f['Workspace']),issue_id=I if f['Bound'] else None,comment_id=I if f.get('Comment') else None,source_context_id=I if f['Historical'] else None,uploader_type=f['UploaderType'],uploader_id=parse_uuid(f['Uploader']) if f['Uploader'] else None,url='https://storage/object')
    def get_attachment(self,*args):self.record('read' if self.transaction else 'load',*args);return self.row()
    def lock_attachment_row(self,*args):self.record('row',*args);return self.row()
    def delete_attachment(self,*args):self.record('delete',*args);return dict(changed=self.f['Changed'],issue_revision=self.f['Revision'])
    def lock_live_comment(self,*args):self.record('comment_lock',*args)
    def get_comment_in_workspace(self,identity,workspace):
        self.record('comment_event',identity,workspace)
        return dict(id=I,issue_id=I,workspace_id=workspace,author_type='member',author_id=self.f['User'],content='body',type='text',revision=self.f['Revision'],created_at=None,updated_at=None)
    def list_reactions_by_comment_ids(self,ids):self.record('reactions',ids);return []
    def list_attachments_by_comment_ids(self,ids,workspace):self.record('attachments',ids,workspace);return []
    def hidden(self,workspace):self.record('hidden',parse_uuid(workspace));return Hidden()
    def key_from_url(self,url):self.record('key',url);return 'object'
    def delete(self,key):self.record('storage',key)
async def evaluate(f):
    q=Queries(f)
    service=AttachmentMutations(q,q.begin,lambda tx:q,q if f['Storage'] else None,None,lambda *args:q.record('publish',*args),
        user_id=f['User'],workspace_id=f['Workspace'],hidden_projects=q.hidden,member=dict(role=f['Role']),
        request_error=lambda:asyncio.CancelledError() if f['Cancelled'] else None)
    response=await service.delete(f['ID'])
    return dict(status=response.status_code,body=json.loads(response.body) if response.body else None,calls=q.calls)
def run(output):
    base=dict(ID=A,Workspace=W,User=U,UploaderType='member',Uploader=U,Role='member',Failure='',Bound=False,Historical=False,Changed=True,Storage=True,Cancelled=False,Revision=0)
    fixtures=[dict(base,Bound=bound,Failure=failure,Cancelled=cancelled) for bound in [False,True] for cancelled in [False,True] for failure in ['',*[name+suffix for name in ['load','hidden','begin','execute','issue','row','read','delete','commit','rollback','storage'] for suffix in ['', '-missing','-cancel']]]]
    fixtures.extend(dict(base,UploaderType=kind,User=user,Role=role,Historical=historical) for kind in ['member','agent'] for user in [U,U.upper(),I,''] for role in ['member','admin','owner','Admin'] for historical in [False,True])
    fixtures.extend(dict(base,ID=identity,Workspace=workspace,User=user) for identity in [A,'invalid'] for workspace in [W,'invalid',''] for user in [U,''])
    fixtures.extend(dict(base,Bound=bound,Changed=changed,Revision=revision,Storage=storage) for bound in [False,True] for changed in [False,True] for revision in [0,5] for storage in [False,True])
    fixtures.extend(dict(base,Comment=True,Bound=bound,Changed=changed,Revision=revision,Failure=failure) for bound in [False,True] for changed in [False,True] for revision in [0,5] for failure in ['', 'comment_lock-missing','comment_event','comment_event-cancel','reactions','attachments'])
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1';binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro','-v',f'{ROOT/"server/tests/parity/go_attachment_deletion"}:/harness:ro','-v',f'{binaries}:/out','-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build','-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=','-e','GOMAXPROCS=4','golang:1.26.9','sh','-c','mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/handler/parity_attachment_deletion.go && cd /work && go build -mod=readonly -p=4 -o /out/attachment-deletion-oracle ./parity'])
    go=[]
    for offset in range(0,len(fixtures),32):
        result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i','-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0','/out/attachment-deletion-oracle'],input=json.dumps(fixtures[offset:offset+32]));go.extend(json.loads(result.stdout))
    python=[asyncio.run(evaluate(f)) for f in fixtures];assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/handler/file.go','server/go/internal/handler/wakeup_actor.go','server/tests/parity/go_attachment_deletion/main.go','server/tests/parity/go_attachment_deletion/wrapper.go','server/tools/run_attachment_deletion_parity.py','server/src/workpal_backend/files/deletion.py','server/src/workpal_backend/files/mutations.py','server/src/workpal_backend/auth/wakeup_actor.py','server/src/workpal_backend/auth/actor.py','server/src/workpal_backend/files/loader.py','server/src/workpal_backend/files/events.py','server/src/workpal_backend/comments/groups.py','server/src/workpal_backend/comments/projection.py','server/src/workpal_backend/infrastructure/go_time.py','server/src/workpal_backend/files/write_transactions.py']
    Path(output).write_text(json.dumps(dict(scope='Original DeleteAttachment versus Python request-scoped AttachmentMutations status/body/query and synchronous event order: unowned/issue-owned attachments, historical immutability, exact uploader/admin authorization, write failures, Changed/revision and best-effort storage. Comment-owner deletion includes original comment reload/group projection and event payload; owner changes separately tested; no physical locks, HTTP middleware or live route activation certification.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)));return bool(mismatches)
if __name__=='__main__':
    try:raise SystemExit(run(sys.argv[1]))
    except subprocess.CalledProcessError as error:print(error.stderr,file=sys.stderr);raise
