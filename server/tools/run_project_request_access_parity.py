"""Original handler hiddenProjects request/run authorization versus Python."""
from pathlib import Path
import hashlib,json,sys,subprocess
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.projects.request_access import hidden_for_request
from workpal_backend.infrastructure.query_errors import NoRows

def uid(i):return f'00000000-0000-0000-0000-{i:012x}'
W,P,U,A,T,O=[uid(i) for i in range(1,7)]
class Queries:
    def __init__(self,f):self.f=f;self.calls=[]
    def record(self,kind,*args):
        self.calls.append([kind,*args])
        if self.f['Failure']==kind:raise RuntimeError('query failed')
        if self.f['Failure']==kind+'-missing':raise NoRows()
    def list_private_project_ids(self,w):self.record('private',w);return [] if self.f['Empty'] else [P]
    def get_task(self,t):self.record('task',t);return dict(originator_user_id=self.f['Originator'] or None,accountable_user_id=self.f['Accountable'] or None)
    def get_agent(self,a):self.record('agent',a);return dict(owner_id=self.f['Owner'] or None)
    def get_member(self,w,u):
        self.record('member',w,u)
        if u==self.f['MissingMember']:raise NoRows()
        return {}
    def list_hidden_project_ids(self,w,u):self.record('hidden',w,u);return [P] if u==self.f['Owner'] else []

def run(output):
    base=dict(Actor='agent',Agent=A,Task=T,User=U,Originator=U,Accountable=A,Owner=O,Failure='',MissingMember='',CtxUser='',CtxWorkspace='',Empty=False)
    fixtures=[{**base,'Originator':originator,'Accountable':accountable,'Owner':owner,'Failure':failure,'Empty':empty} for originator in [U,''] for accountable in [A,U,''] for owner in [O,U,''] for failure in ['','private','task','task-missing','agent','agent-missing','member','hidden'] for empty in [False,True]]
    fixtures.extend({**base,'Agent':agent,'Task':task} for agent in ['', 'invalid', A] for task in ['', 'invalid',T])
    fixtures.extend({**base,'MissingMember':member} for member in [U,A,O])
    fixtures.extend({**base,'Actor':'member','User':user,'CtxUser':ctx,'CtxWorkspace':workspace,'Failure':failure} for user in [U,'invalid',''] for ctx,workspace in [('', ''),(U,W),(O,W),(U,O)] for failure in ['','member','hidden','private'])
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_project_request_access"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/handler/parity_project_request_access.go && cd /work && go build -mod=readonly -p=4 -o /out/project-request-access-oracle ./parity'])
    go=[]
    for offset in range(0,len(fixtures),32):
        result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i','-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0','/out/project-request-access-oracle'],input=json.dumps(fixtures[offset:offset+32]))
        go.extend(json.loads(result.stdout))
    python=[]
    for f in fixtures:
        queries=Queries(f);ids=[];error=False
        member=dict(workspace_id=f['CtxWorkspace'],user_id=f['CtxUser']) if f['CtxUser'] else None
        try:ids=hidden_for_request(queries,W,f['User'],f['Actor'],f['Agent'] if f['Actor']=='agent' else f['User'],task_id=f['Task'],context_member=member).ids()
        except Exception:error=True
        python.append(dict(ids=ids,error=error,calls=queries.calls))
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/handler/project_access.go','server/go/internal/projectaccess/projectaccess.go','server/go/internal/handler/handler.go','server/go/pkg/db/generated/agent.sql.go','server/go/pkg/db/generated/member.sql.go','server/go/pkg/db/generated/project_member.sql.go','server/tests/parity/go_project_request_access/main.go','server/tests/parity/go_project_request_access/wrapper.go','server/src/workpal_backend/projects/request_access.py','server/src/workpal_backend/projects/access.py','server/src/workpal_backend/infrastructure/go_uuid.py','server/tools/run_project_request_access_parity.py']
    Path(output).write_text(json.dumps(dict(scope='Actual hiddenProjects/hiddenProjectsForAgentRun through original generated DB queries with strict row fixtures: hidden IDs, query order/arguments and error outcome, task originator/accountable fallback, agent owner, missing records and matching context-member fast path. Agent actor uses trusted task_token fixture headers; does not certify HTTP header stripping, real DB/schema or full attachment routes.',fixtures=fixtures,execution_batch_size=32,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':
    try:raise SystemExit(run(sys.argv[1]))
    except subprocess.CalledProcessError as error:
        print(error.stderr,file=sys.stderr)
        raise
