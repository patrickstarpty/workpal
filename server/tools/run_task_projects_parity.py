"""Actual Go TasksProjects against isolated query fixtures."""
from pathlib import Path
import hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.realtime.task_projects import tasks_projects

def run(output):
    P,P2,I,R=[f'00000000-0000-0000-0000-{i:012d}' for i in range(1,5)]
    fixtures=[]
    def add(tasks,failure=''):fixtures.append(dict(Tasks=tasks,Failure=failure))
    contexts=[json.dumps(dict(type='quick_create',project_id=P,parent_issue_id=I)),
        '{"TYPE":"quick_create","PROJECT_ID":"'+P+'"}',
        '{"type":"quick_create","project_id":"'+P+'","project_id":null}',
        '{"type":"quick_create","project_id":7,"project_id":"'+P+'"}',
        '{"type":"quick_create","project_id":"'+P+'"} {}',
        '{"type":"quick_create","project_id":"'+P+'","unknown":1e999}',
        '{"type":"quick_create","project_id":"'+P+'","unknown":'+('9'*5000)+'}',
        'null','[]','not json','',json.dumps(dict(type='quick_create',project_id='bad',parent_issue_id=I)),
        json.dumps(dict(type='quick_create',project_id=P,parent_issue_id='bad'))]
    for raw in contexts:add([dict(context=raw)])
    add([dict(autopilot_run_id=R)]*200+[dict(issue_id=I,chat_session_id=R,autopilot_run_id=R),dict(chat_session_id=R,autopilot_run_id=R),dict(context=contexts[0]),{}])
    add([])
    for failure in ['issue','run']:add([dict(issue_id=I),dict(autopilot_run_id=R)],failure)
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_task_projects"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cd /work && go build -mod=readonly -p=4 -o /out/task-projects-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/task-projects-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    python=[]
    class Queries:
        def __init__(self,failure):self.failure=failure;self.calls=[]
        def record(self,kind,ids):
            self.calls.append(dict(kind=kind,ids=sorted(ids)))
            if self.failure==kind:raise RuntimeError('db down')
        def list_issue_project_ids(self,ids):self.record('issue',ids);return [(I,P2)]
        def list_autopilot_run_project_ids(self,ids):self.record('run',ids);return [(identity,P) for identity in ids]
    for fixture in fixtures:
        q=Queries(fixture['Failure']);error=''
        try:projects=tasks_projects(q,fixture['Tasks'])
        except Exception as exc:projects=None;error=str(exc)
        python.append(dict(projects=projects,calls=q.calls,error=error))
    if len(go)!=len(python):raise RuntimeError('missing observations')
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/projectaccess/task.go','server/tests/parity/go_task_projects/main.go','server/src/workpal_backend/realtime/task_projects.py']
    Path(output).write_text(json.dumps(dict(scope='Actual Go TasksProjects: ordered task outputs, errors, query sequence and requested ID sets. Query ID order is explicitly compared as sets because Go iterates a map. No actual SQL/authorization/transport coverage.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},binary_sha256=hashlib.sha256((binaries/'task-projects-oracle').read_bytes()).hexdigest()),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
