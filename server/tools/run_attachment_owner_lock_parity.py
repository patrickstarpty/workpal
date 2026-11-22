"""Original owner-lock transaction control flow; physical locks are not simulated."""
from pathlib import Path
import hashlib,json,sys,subprocess
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.files.write_transactions import AttachmentWriter
from workpal_backend.infrastructure.query_errors import NoRows
from asyncio import CancelledError
A='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';W='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
I='cccccccc-cccc-cccc-cccc-cccccccccccc';C='dddddddd-dddd-dddd-dddd-dddddddddddd'
class Queries:
    def __init__(self,f):self.f=f;self.calls=[];self.attempt=-1
    def record(self,kind,*args):
        self.calls.append([kind,*args]);failure=self.f['Failure']
        if failure==kind:raise RuntimeError(kind+' failed')
        if failure==kind+'-missing':raise NoRows()
        if failure==kind+'-cancel':raise CancelledError()
    def begin(self):self.attempt+=1;self.record('begin');return self
    def commit(self):self.record('commit')
    def rollback(self):self.record('rollback')
    def lock_issue_for_attachment_write(self,*args):self.record('issue',*args)
    def lock_live_comment(self,*args):self.record('comment',*args)
    def read(self,kind,*args):
        self.record(kind,*args);return row(self.f['Fresh'][min(self.attempt,len(self.f['Fresh'])-1)])
    def get_attachment(self,*args):return self.read('read',*args)
    def lock_attachment_row(self,*args):return self.read('row',*args)
def row(owners):return dict(id=A,workspace_id=W,issue_id=owners[0] or None,comment_id=owners[1] or None)
def evaluate(f):
    q=Queries(f);writer=AttachmentWriter(q.begin,lambda tx:q);message=''
    try:writer.with_owner_lock(row(f['Initial']),lambda queries:q.record('write'))
    except NoRows:message='no rows in result set'
    except CancelledError:message='context canceled'
    except Exception as error:message=str(error)
    return dict(calls=q.calls,error=message)
def run(output):
    owners=[['',''],[I,''],['',C],[I,C]]
    fixtures=[dict(Initial=initial,Fresh=[fresh,fresh],Failure=failure) for initial in owners for fresh in owners for failure in ['',*[name+suffix for name in ['begin','issue','comment','row','read','write','commit','rollback'] for suffix in ['', '-missing','-cancel']]]]
    fixtures.extend(dict(Initial=['',''],Fresh=[[I,''],[I,C],['',C]],Failure=failure) for failure in ['','write','rollback'])
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1';binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro','-v',f'{ROOT/"server/tests/parity/go_attachment_owner_lock"}:/harness:ro','-v',f'{binaries}:/out','-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build','-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=','-e','GOMAXPROCS=4','golang:1.26.9','sh','-c','mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/handler/parity_attachment_owner.go && cd /work && go build -mod=readonly -p=4 -o /out/attachment-owner-oracle ./parity'])
    go=[]
    for offset in range(0,len(fixtures),32):
        result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i','-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0','/out/attachment-owner-oracle'],input=json.dumps(fixtures[offset:offset+32]));go.extend(json.loads(result.stdout))
    python=[evaluate(f) for f in fixtures];assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/handler/file.go','server/go/internal/handler/wakeup_actor.go','server/tests/parity/go_attachment_owner_lock/main.go','server/tests/parity/go_attachment_owner_lock/wrapper.go','server/tools/run_attachment_owner_lock_parity.py','server/src/workpal_backend/files/write_transactions.py']
    Path(output).write_text(json.dumps(dict(scope='Original withAttachmentOwnerLock control flow, generated query scans, retry bound and error/rollback propagation. Fixture transactions, not physical SQL row locks, isolation or concurrent writer certification.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)));return bool(mismatches)
if __name__=='__main__':
    try:raise SystemExit(run(sys.argv[1]))
    except subprocess.CalledProcessError as error:print(error.stderr,file=sys.stderr);raise
