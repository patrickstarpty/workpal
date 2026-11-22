"""Original Go scope authorizer with isolated resource queries."""
from pathlib import Path
import hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.realtime.scope_authorizer import ScopeAuthorizer
from workpal_backend.infrastructure.query_errors import NoRows

def run(output):
    def uid(i):return f'00000000-0000-0000-0000-{i:012x}'
    U,W,S,T,I=map(uid,range(1,6))
    fixtures=[]
    def add(**fields):
        f=dict(Scope='chat',User=U,Workspace=W,ID=S,Issue=False,Orphan=False,Failure='',Missing=False);f.update(fields);fixtures.append(f)
    add();add(User=uid(9));add(User='');add(Workspace=uid(9));add(Workspace='bad');add(ID='bad');add(Scope='unknown')
    add(Scope='task',ID=T);add(Scope='task',ID=T,User=uid(9));add(Scope='task',ID=T,Issue=True,User='');add(Scope='task',ID=T,Orphan=True)
    for scope,stage in [('task','task'),('task','chat'),('task','issue'),('chat','chat')]:
        for missing in [False,True]:add(Scope=scope,ID=T if scope=='task' else S,Issue=stage=='issue',Failure=stage,Missing=missing)
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_scope_authorizer"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /work/cmd/server/scope_authorizer.go /work/parity/scope_authorizer.go && cd /work && go build -mod=readonly -p=4 -o /out/scope-authorizer-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/scope-authorizer-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    python=[]
    class Queries:
        def __init__(self,f):self.f=f;self.calls=[]
        def read(self,name,row):
            self.calls.append(name)
            if self.f['Failure']==name:
                if self.f['Missing']:raise NoRows()
                raise RuntimeError('database down')
            return row
        def get_task(self,id):return self.read('task',dict(issue_id=I if self.f['Issue'] else None,chat_session_id=None if self.f['Orphan'] else S))
        def get_issue(self,id):return self.read('issue',dict(workspace_id=W))
        def get_chat_session(self,id):return self.read('chat',dict(workspace_id=W,creator_id=U))
    for f in fixtures:
        q=Queries(f);message=''
        try:allowed=ScopeAuthorizer(q)(f['User'],f['Workspace'],f['Scope'],f['ID'])
        except Exception as exc:allowed=False;message=str(exc)
        python.append(dict(allowed=allowed,error=message,calls=q.calls))
    if len(go)!=len(python):raise RuntimeError('missing observations')
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/cmd/server/scope_authorizer.go','server/tests/parity/go_scope_authorizer/main.go','server/src/workpal_backend/realtime/scope_authorizer.py','server/src/workpal_backend/infrastructure/query_errors.py']
    Path(output).write_text(json.dumps(dict(scope='Original scope authorizer decision/error/query order against isolated rows. No frame decoder, transport, SQL or revocation timing equivalence certified.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},binary_sha256=hashlib.sha256((binaries/'scope-authorizer-oracle').read_bytes()).hexdigest()),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
