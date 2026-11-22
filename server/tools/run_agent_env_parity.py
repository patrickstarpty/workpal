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
    agent='40000000-0000-4000-8000-000000000001'
    common.append(f"INSERT INTO agent(id,workspace_id,name,runtime_mode,owner_id,custom_env) VALUES ('{agent}','{W}','Env fixture','local','{M}','{{\"Z_KEY\":\"fixture-z\",\"A_KEY\":\"fixture-a\"}}')")
    pg_seeds=common.copy()
    path='/api/agents/'+agent+'/env'
    cases=[dict(Path=p,User=user,Query=query,Headers={},SQL=sql) for p,user,query,sql in [
        (path,M,'workspace_slug=fixture',''),(path,U,'workspace_slug=fixture',''),
        (path,X,'workspace_slug=fixture',''),('/api/agents/bad/env',M,'workspace_slug=fixture',''),
        (path,M,'',''),(path,M,'workspace_id=nope',''),
        (path,M,'workspace_slug=fixture',"UPDATE agent SET owner_id=NULL"),
        (path,U,'workspace_slug=fixture',"UPDATE agent SET kind='system'"),
        (path,U,'workspace_slug=fixture',"UPDATE agent SET kind='user',custom_env='null'"),
        (path,U,'workspace_slug=fixture',"UPDATE agent SET custom_env='{\"a\":null}'"),
        (path,U,'workspace_slug=fixture',"UPDATE agent SET custom_env='{\"a\":42}'"),
        (path,U,'workspace_slug=fixture',"UPDATE agent SET custom_env='[1]'"),
        (path,U,'workspace_slug=fixture',"UPDATE agent SET custom_env='{\"dup\":\"first\",\"dup\":\"last\"}'"),
        (path,U,'workspace_slug=fixture',"ALTER TABLE activity_log ADD CONSTRAINT fixture_outage CHECK(action <> 'agent_env_revealed') NOT VALID")]]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_agent_env"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cd /work && go build -mod=readonly -p=4 -o /out/agent-env-oracle ./parity'])
    go=[]
    def observe(container):
        result=command(['docker','run','--rm','--platform','linux/amd64','--network',container.removesuffix('-db'),
            '-i','-e',f'DATABASE_URL=postgres://postgres@{container}:5432/parity?sslmode=disable',
            '-v',f'{binaries}:/out:ro',
            'sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0','/out/agent-env-oracle'],
            input=json.dumps(dict(Seeds=pg_seeds,Cases=cases)))
        go.extend(json.loads(result.stdout))
        return go
    python=[]
    with tempfile.TemporaryDirectory(prefix='workpal-agent-env-') as tmp:
        export_schema(Path(tmp)/'schema.json',observe)
        settings=Settings(database_url='sqlite:///'+tmp+'/fixture.sqlite',redis_url='redis://127.0.0.1:1',auth_secret=SECRET)
        migrate(settings)
        app=create_app(settings)
        with TestClient(app) as client:
            with app.state.database.transaction() as session:
                for sql in common:
                    sql=sql.replace('INTO "user"','INTO users').replace('INTO workspace(','INTO workspaces(').replace('INTO member(','INTO members(')
                    session.execute(text(sql))
            for case in cases:
                if case['SQL']:
                    with app.state.database.transaction() as session:
                        if case['SQL'].startswith('ALTER TABLE'):
                            session.execute(text("CREATE TRIGGER fixture_outage BEFORE INSERT ON activity_log BEGIN SELECT RAISE(ABORT,'fixture audit outage'); END"))
                        else:session.connection().exec_driver_sql(case['SQL'])
                token=issue_session(case['User'],'fixture@example.com','Fixture',SECRET,3600)
                response=client.get(case['Path']+'?'+case['Query'],headers={'Authorization':'Bearer '+token})
                with app.state.database.transaction() as session:
                    audits=[dict(row) for row in session.execute(text('SELECT workspace_id,issue_id,actor_type,actor_id,action,details FROM activity_log ORDER BY created_at,id')).mappings()]
                for row in audits:row['details']=json.loads(row['details'])
                python.append(dict(status=response.status_code,body=response.text,audits=audits))
    if len(go)!=len(python):raise RuntimeError('missing observations')
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a['status']!=b['status'] or a['body']!=b['body'] or a['audits']!=b['audits']]
    sources=['server/go/internal/handler/agent_env.go','server/go/internal/handler/handler.go',
        'server/go/internal/middleware/workspace.go','server/tests/parity/go_agent_env/main.go',
        'server/src/workpal_backend/agents/env.py','server/migrations/versions/0017_activity_log.py']
    evidence=dict(source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},scope='Agent env reveal handler + workspace middleware status/body and audit fields; actual PostgreSQL/SQLite. UUIDv7 audit IDs and timestamps nondeterministic and excluded; full auth/task/CloudFront/transport not compared.',
        fixtures=cases,pg_seed=pg_seeds,go=go,python=python,mismatches=mismatches,
        binary_sha256=hashlib.sha256((binaries/'agent-env-oracle').read_bytes()).hexdigest())
    Path(output).write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps(dict(cases=len(cases),mismatches=mismatches)))
    return bool(mismatches)

if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
