"""Compare original private-project audience caching with isolated query fixtures."""
from pathlib import Path
import hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.realtime.private_projects import PrivateProjectAudience

def run(output):
    W,T,P,P2,I,U,V=[f'00000000-0000-0000-0000-{i:012d}' for i in range(1,8)]
    def step(kind='task:message',time=0,rows=None,projects=None,fail=False,payload=None):
        return dict(Event=dict(type=kind,workspaceID=W,taskID=T,payload=payload or {}),Time=time,Rows=rows if rows is not None else [[P,U],[P,V],[P2,V]],Projects=projects if projects is not None else [P],Fail=fail)
    scripts=[
        [step(),step(),step(time=1.999,rows=[[P,V]]),step(time=2,rows=[[P,None]])],
        [step(projects=[P,P2],rows=[[P,U],[P,V],[P,V],[P2,V]]),step(kind='unknown',payload={'issue':{'project_id':P}})],
        [step(fail=True),step(),step(kind='project:members_changed',rows=[[P,V]],payload={'project_id':P}),step(rows=[[P,V]])],
    ]
    for kind in ['issue:updated','autopilot:updated','project:updated','member:updated','task:queued','task:completed','task:failed','task:cancelled']:
        scripts.append([step(),step(kind=kind,projects=[P2]),step(projects=[P2])])
    scripts.append([step(kind=kind,fail=True) for kind in ['task:coalesced','task:dispatch','task:running','task:waiting_local_directory','task:usage']])
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_private_audience"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /work/cmd/server/private_project_realtime.go /work/parity/private_project_realtime.go && cd /work && go build -mod=readonly -p=4 -o /out/private-audience-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/private-audience-oracle'],input=json.dumps(scripts))
    go=json.loads(result.stdout)
    python=[]
    class Queries:
        def __init__(self):self.calls=[]
        def list_private_project_audience(self,w):
            self.calls.append('workspace')
            if self.state['Fail']:raise RuntimeError('database down')
            return self.state['Rows']
        def get_task(self,t):
            self.calls.append('task');context={'type':'quick_create'}
            if self.state['Projects']:context['project_id']=self.state['Projects'][0]
            if len(self.state['Projects'])>1:context['parent_issue_id']=I
            return dict(context=json.dumps(context))
        def list_issue_project_ids(self,ids):
            self.calls.append('projects');return [(I,self.state['Projects'][1])]
    for script in scripts:
        q=Queries();a=PrivateProjectAudience(q,now=lambda:q.state['Time']);results=[]
        for state in script:
            q.state=state;message=''
            try:members,private=a(state['Event'])
            except Exception as exc:members,private=None,False;message=str(exc)
            results.append(dict(members=members,private=private,error=message,calls=q.calls[:]))
        python.append(results)
    if len(go)!=len(python):raise RuntimeError('missing observations')
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/cmd/server/private_project_realtime.go','server/go/internal/projectaccess/task.go','server/tests/parity/go_private_audience/main.go','server/src/workpal_backend/realtime/private_projects.py','server/src/workpal_backend/realtime/event_refs.py','server/src/workpal_backend/realtime/task_projects.py','server/src/workpal_backend/infrastructure/query_errors.py']
    Path(output).write_text(json.dumps(dict(scope='Actual Go audience cache with isolated query state changes; compares recipients/private/errors/cumulative query calls. Includes real Python task-project extraction; SQL, deadlines, threading and transport are not certified.',scripts=scripts,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},binary_sha256=hashlib.sha256((binaries/'private-audience-oracle').read_bytes()).hexdigest()),indent=2)+'\n')
    print(json.dumps(dict(scripts=len(scripts),observations=sum(map(len,scripts)),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
