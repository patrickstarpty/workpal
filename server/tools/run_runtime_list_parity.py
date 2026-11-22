"""Actual Go runtime list + workspace middleware against Python HTTP; isolated data."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
from export_go_schema import run as export_schema,command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from fastapi.testclient import TestClient
from sqlalchemy import text
from workpal_backend.app import create_app
from workpal_backend.auth.tokens import issue_session
from workpal_backend.infrastructure.database import migrate
from workpal_backend.config import Settings
SECRET='fixture-runtime-secret-'*4
U='10000000-0000-4000-8000-000000000001'
M='10000000-0000-4000-8000-000000000002'
X='10000000-0000-4000-8000-000000000003'
W='20000000-0000-4000-8000-000000000001'
stamp="'2026-01-01T01:02:03Z'"

def run(output):
    common=[]
    for user in [U,M,X]:
        common.append(f"""INSERT INTO "user"(id,name,email,created_at,updated_at) VALUES ('{user}','Fixture','{user}@example.com',{stamp},{stamp})""")
    common.append(f"INSERT INTO workspace(id,name,slug,issue_prefix,created_at,updated_at) VALUES ('{W}','Fixture','fixture','FX',{stamp},{stamp})")
    for i,(user,role) in enumerate([(U,'owner'),(M,'member')]):
        common.append(f"INSERT INTO member(id,workspace_id,user_id,role,created_at) VALUES ('30000000-0000-4000-8000-00000000000{i}','{W}','{user}','{role}',{stamp})")
    runtime_seeds=[]
    for i,(name,owner,visibility,shared,metadata,provider) in enumerate([
        ('Mine',M,'private',[],{},'omp'),('Private',U,'private',[],None,'claude'),
        ('Shared',U,'private',[None,M.upper()],{'z':1.0,'a':2},'codex'),('Public',None,'public',[],
            {'large':9007199254740993,'fraction':1e-7,'small':1e-6,'nested':{'z':-0.0,'a':1e20}},'unknown'),('Overflow',U,'public',[],'__overflow__','claude')]):
        rid=f'40000000-0000-4000-8000-00000000000{i}'
        values=dict(id=rid,workspace_id=W,name=name,runtime_mode='local',provider=provider,
                    owner_id=owner,visibility=visibility,metadata='{"overflow":1e999,"fine":1,"dup":1,"dup":{}}' if metadata=='__overflow__' else
                        '{"z":1.0,"a":2,"a":1}' if name=='Shared' else json.dumps(metadata),
                    created_at=f'2026-01-0{i+1}T01:02:03.456789Z',updated_at='2026-01-01T01:02:03Z')
        if name in ('Mine','Shared','Public'):
            values['created_at']={'Mine':'2026-01-01T00:00:00Z','Shared':'2026-01-01T00:00:00.1Z',
                                  'Public':'2026-01-01T01:00:00.2+01:00'}[name]
        runtime_seeds.append((values,shared))
    def literal(value):return 'NULL' if value is None else "'"+str(value).replace("'","''")+"'"
    pg_seeds=common.copy()
    for values,shared in runtime_seeds:
        pg_seeds.append('INSERT INTO agent_runtime ('+','.join(values)+',shared_with) VALUES ('+
            ','.join(literal(v) for v in values.values())+",'{"+','.join('NULL' if v is None else v for v in shared)+"}')")
    cases=[dict(User=user,Query=query,Headers=headers) for user,query,headers in [
        (U,'workspace_slug=fixture',{}),(M,'workspace_slug=fixture',{}),(X,'workspace_slug=fixture',{}),
        (U,'workspace_slug=fixture&owner=me',{}),(M,'workspace_slug=fixture&owner=me',{}),
        (M,'workspace_slug=fixture&owner=me&owner=other',{}),(M,'',{}),
        (M,'workspace_id=nope',{}),(M,'workspace_slug=unknown',{'X-Workspace-ID':W}),
        (M,'workspace_slug=fixture',{'X-Workspace-Slug':'unknown'}),
        (M,'workspace_slug=unknown',{'X-Workspace-Slug':'fixture'}),
        (M,'workspace_id=%zz',{'X-Workspace-ID':W}),
        ('invalid','workspace_id='+W,{})]]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_runtime_list"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cd /work && go build -mod=readonly -p=4 -o /out/runtime-list-oracle ./parity'])
    go=[]
    def observe(container):
        result=command(['docker','run','--rm','--platform','linux/amd64','--network',container.removesuffix('-db'),
            '-i','-e',f'DATABASE_URL=postgres://postgres@{container}:5432/parity?sslmode=disable',
            '-v',f'{binaries}:/out:ro',
            'sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0','/out/runtime-list-oracle'],
            input=json.dumps(dict(Seeds=pg_seeds,Cases=cases)))
        go.extend(json.loads(result.stdout))
        return go
    python=[]
    with tempfile.TemporaryDirectory(prefix='workpal-runtime-list-') as tmp:
        export_schema(Path(tmp)/'schema.json',observe)
        settings=Settings(database_url='sqlite:///'+tmp+'/fixture.sqlite',redis_url='redis://127.0.0.1:1',auth_secret=SECRET)
        migrate(settings)
        app=create_app(settings)
        with TestClient(app) as client:
            with app.state.database.transaction() as session:
                for sql in common:
                    sql=sql.replace('INTO "user"','INTO users').replace('INTO workspace(','INTO workspaces(').replace('INTO member(','INTO members(')
                    session.execute(text(sql))
                for values,shared in runtime_seeds:
                    values=values|{'shared_with':json.dumps(shared)}
                    session.execute(text('INSERT INTO agent_runtime ('+','.join(values)+') VALUES ('+
                        ','.join(':'+k for k in values)+')'),values)
            for case in cases:
                token=issue_session(case['User'],'fixture@example.com','Fixture',SECRET,3600)
                response=client.get('/api/runtimes?'+case['Query'],headers=case['Headers']|{'Authorization':'Bearer '+token})
                python.append(dict(status=response.status_code,body=response.text,headers=dict(response.headers)))
    if len(go)!=len(python):raise RuntimeError('missing observations')
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a['status']!=b['status'] or a['body']!=b['body']]
    sources=['server/go/internal/handler/runtime.go','server/go/pkg/db/queries/runtime.sql',
        'server/go/internal/middleware/workspace.go','server/go/pkg/agent/agent.go',
        'server/go/pkg/agent/builtin_runtimes.go','server/tests/parity/go_runtime_list/main.go',
        'server/src/workpal_backend/runtimes/routes.py','server/src/workpal_backend/runtimes/projection.py',
        'server/src/workpal_backend/workspaces/admission.py','server/src/workpal_backend/infrastructure/go_response.py',
        'server/src/workpal_backend/infrastructure/sqlite_compat.py','server/src/workpal_backend/infrastructure/go_json_value.py']
    evidence=dict(source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},scope='Runtime list handler and workspace middleware status/body; seeded actual PostgreSQL/SQLite. Full auth/CloudFront/transport framing not compared.',
        fixtures=cases,pg_seed=pg_seeds,go=go,python=python,mismatches=mismatches,
        binary_sha256=hashlib.sha256((binaries/'runtime-list-oracle').read_bytes()).hexdigest())
    Path(output).write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps(dict(cases=len(cases),mismatches=mismatches)))
    return bool(mismatches)

if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
