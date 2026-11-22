"""Original attachment parent visibility/filter helpers against Python."""
from pathlib import Path
import hashlib,json,sys,subprocess
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.files.access import attachment_in_hidden_project,visible_attachment_ids
from workpal_backend.projects.access import for_member
from workpal_backend.infrastructure.query_errors import NoRows

def uid(i):return f'00000000-0000-0000-0000-{i:012x}'
W,P,I,C,U,A,B=[uid(i) for i in range(1,8)]
class Queries:
    def __init__(self,f):self.f=f;self.calls=[]
    def record(self,kind,*args):
        self.calls.append([kind,*args])
        if self.f['Failure']==kind:raise RuntimeError('query failed')
        if self.f['Failure']==kind+'-missing':raise NoRows()
    def list_hidden_project_ids(self,w,u):self.record('hidden',w,u);return [] if self.f['Empty'] else [P]
    def issue_project(self,identity):self.record('issue',identity);return self.f['Project'] or None
    def comment_project(self,identity):self.record('comment',identity);return self.f['Project'] or None
    def attachment(self,identity):return dict(id=identity,workspace_id=W,issue_id=I if identity==A and self.f['Issue'] else None,comment_id=C if identity==A and self.f['Comment'] else None)
    def list_attachments_by_ids(self,w,ids):self.record('attachments',w,ids);return [self.attachment(v) for v in [A,B] if v in ids]

def run(output):
    fixtures=[]
    for issue in [False,True]:
        for comment in [False,True]:
            for empty in [False,True]:
                for project in ['',P,uid(99)]:
                    for failure in ['','hidden','issue','issue-missing','comment','comment-missing','attachments']:
                        base=dict(Issue=issue,Comment=comment,Empty=empty,Project=project,Failure=failure)
                        fixtures.append(dict(base,Mode='single',IDs=None))
                        for ids in [None,[],[A,B,uid(99),A,B]]:fixtures.append(dict(base,Mode='filter',IDs=ids))
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_attachment_access"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/handler/parity_attachment_access.go && cd /work && go build -mod=readonly -p=4 -o /out/attachment-access-oracle ./parity'])
    go=[]
    for offset in range(0,len(fixtures),32):
        result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i','-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0','/out/attachment-access-oracle'],input=json.dumps(fixtures[offset:offset+32]))
        go.extend(json.loads(result.stdout))
    python=[]
    for f in fixtures:
        q=Queries(f);hidden=False;error=False;ids=None
        try:
            if f['Mode']=='single':hidden=attachment_in_hidden_project(q,for_member(q,W,U),q.attachment(A))
            elif not f['IDs']:ids=f['IDs']
            else:ids=visible_attachment_ids(q,for_member(q,W,U),W,f['IDs'])
        except Exception:error=True
        python.append(dict(hidden=hidden,error=error,ids=ids,calls=q.calls))
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/handler/project_access.go','server/go/internal/projectaccess/projectaccess.go','server/go/pkg/db/generated/attachment.sql.go','server/go/pkg/db/generated/project_member.sql.go','server/tests/parity/go_attachment_access/main.go','server/tests/parity/go_attachment_access/wrapper.go','server/src/workpal_backend/files/access.py','server/src/workpal_backend/projects/access.py','server/src/workpal_backend/infrastructure/go_uuid.py','server/tools/run_attachment_access_parity.py']
    Path(output).write_text(json.dumps(dict(scope='Actual attachmentInHiddenProject/visibleAttachmentIDs with original generated DB queries and strict fixtures: issue-before-comment precedence, missing parents, errors, nil/empty/duplicates/missing IDs and query arguments/order. Hidden request context is a known member. No full HTTP authentication/status/body or canonical attachment DB migration certification.',fixtures=fixtures,execution_batch_size=32,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':
    try:raise SystemExit(run(sys.argv[1]))
    except subprocess.CalledProcessError as error:
        print(error.stderr,file=sys.stderr)
        raise
