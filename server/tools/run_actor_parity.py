"""Actual Go resolveActor against Python with strict isolated DB rows."""
from pathlib import Path
import asyncio,hashlib,json,sys,subprocess
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.auth.actor import resolve_actor
from workpal_backend.infrastructure.query_errors import NoRows
from workpal_backend.infrastructure.go_uuid import parse_uuid
W='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
A='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
T='cccccccc-cccc-cccc-cccc-cccccccccccc'
class Queries:
    def __init__(self,f):self.f=f;self.calls=[]
    def read(self,kind,identity,field):
        self.calls.append([kind,identity])
        if self.f['Failure']==kind:raise RuntimeError('query failed')
        if self.f['Failure']==kind+'-missing':raise NoRows()
        if self.f['Failure']==kind+'-cancel':raise asyncio.CancelledError()
        value=self.f[field]
        return parse_uuid(value) if value else None
    def get_agent(self,identity):return dict(workspace_id=self.read('agent',identity,'StoredWorkspace'))
    def get_task(self,identity):return dict(agent_id=self.read('task',identity,'StoredAgent'))

def run(output):
    base=dict(Source='',User='user',Workspace=W,Agent=A,Task=T,StoredWorkspace=W,StoredAgent=A,Failure='')
    fixtures=[dict(base,Source=source,Agent=agent,Task=task) for source in ['','task_token','TASK_TOKEN'] for agent in ['', 'invalid', A,A.upper(),A.replace('-',''),A.replace('-','X')] for task in ['', 'invalid',T,T.upper(),T.replace('-','')]]
    fixtures.extend(dict(base,Workspace=workspace,StoredWorkspace=stored,StoredAgent=agent,Failure=failure) for workspace in [W,W.upper(),''] for stored in [W,T,''] for agent in [A,W,''] for failure in ['', 'agent','agent-missing','agent-cancel','task','task-missing','task-cancel'])
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_actor"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/handler/parity_actor.go && cd /work && go build -mod=readonly -p=4 -o /out/actor-oracle ./parity'])
    go=[]
    for offset in range(0,len(fixtures),32):
        result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i','-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0','/out/actor-oracle'],input=json.dumps(fixtures[offset:offset+32]))
        go.extend(json.loads(result.stdout))
    python=[]
    for f in fixtures:
        q=Queries(f)
        actor=resolve_actor(q,f['User'],f['Workspace'],actor_source=f['Source'],agent_id=f['Agent'],task_id=f['Task'])
        python.append(dict(actor=list(actor),calls=q.calls))
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/handler/handler.go','server/go/pkg/db/generated/agent.sql.go','server/tests/parity/go_actor/main.go','server/tests/parity/go_actor/wrapper.go','server/src/workpal_backend/auth/actor.py','server/src/workpal_backend/infrastructure/go_uuid.py','server/tools/run_actor_parity.py']
    Path(output).write_text(json.dumps(dict(scope='Actual resolveActor: trusted task_token signal and legacy ID-pair fallback, exact actor IDs and DB query order/args, missing/mismatched identities/errors/cancellation. DB rows isolated; not HTTP spoofed-header stripping or full token authentication certification.',fixtures=fixtures,execution_batch_size=32,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':
    try:raise SystemExit(run(sys.argv[1]))
    except subprocess.CalledProcessError as error:
        print(error.stderr,file=sys.stderr)
        raise
