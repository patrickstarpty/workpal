"""Invoke original Go projectaccess with recorded isolated membership queries."""
from pathlib import Path
import hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.projects.access import Hidden,for_member,for_principals,NoRows

def run(output):
    def uid(i):return f'00000000-0000-0000-0000-{i:012x}'
    P,P2,W=uid(101),uid(102),uid(200)
    fixtures=[dict(Principals=[uid(i) if i else None for i in ids],Failure='',Empty=False,Member=False) for ids in [[1],[2],[5],[6],[1,2],[2,3],[1,4],[],[0,2],[2,2,0]]]
    fixtures += [dict(Principals=[uid(1)],Failure=stage,Empty=False,Member=False) for stage in ['private','member','hidden']]
    fixtures += [dict(Principals=[uid(4)],Failure='member',Empty=True,Member=False),dict(Principals=[uid(1)],Failure='',Empty=False,Member=True)]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_project_access"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cd /work && go build -mod=readonly -p=4 -o /out/project-access-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/project-access-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    python=[]
    class Queries:
        def __init__(self,fixture):self.fixture=fixture;self.calls=[]
        def record(self,kind,user=None):
            self.calls.append([kind,user])
            if self.fixture['Failure']==kind:raise RuntimeError('database down')
        def list_private_project_ids(self,w):self.record('private');return [] if self.fixture['Empty'] else [P,P2]
        def get_member(self,w,u):
            self.record('member',u)
            if u==uid(4):raise NoRows()
            return {'role':{uid(5):'admin',uid(6):'owner'}.get(u,'member')}
        def list_hidden_project_ids(self,w,u):self.record('hidden',u);return [] if u==uid(1) else [P2] if u==uid(2) else [P,P2]
    for fixture in fixtures:
        q=Queries(fixture);error=''
        try:h=for_member(q,W,fixture['Principals'][0]) if fixture['Member'] else for_principals(q,W,*fixture['Principals'])
        except Exception as exc:h=Hidden();error=str(exc)
        python.append(dict(ids=h.ids(),param=h.param(),empty=h.empty(),see=[h.can_see_project(identity) for identity in [P,P2,None]],calls=q.calls,error=error))
    if len(go)!=len(python):raise RuntimeError('missing observations')
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/projectaccess/projectaccess.go','server/tests/parity/go_project_access/main.go','server/src/workpal_backend/projects/access.py','server/src/workpal_backend/infrastructure/query_errors.py']
    Path(output).write_text(json.dumps(dict(scope='Original Go ForMember/ForPrincipals/Hidden visibility with isolated membership queries, role non-bypass, error sequence, duplicate/null principals. SQL, raw HTTP inputs and route wiring not certified. Python exceptions mapped to Go error plus zero-value Hidden only for observation.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},binary_sha256=hashlib.sha256((binaries/'project-access-oracle').read_bytes()).hexdigest()),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
