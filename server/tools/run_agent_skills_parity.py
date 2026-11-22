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
    for i,(name,enabled,config) in enumerate([('Z skill',False,'null'),('A skill',True,'{"z":1,"a":2,"a":1}')]):
        skill=f'50000000-0000-4000-8000-00000000000{i}'
        common.append(f"INSERT INTO skill(id,workspace_id,name,content,config,created_at,updated_at) VALUES ('{skill}','{W}','{name}','fixture body; never execute','{config}',{stamp},{stamp})")
        common.append(f"INSERT INTO agent_skill(agent_id,skill_id,enabled) VALUES ('{agent}','{skill}',{str(enabled).lower()})")
    pg_seeds=common.copy()
    path='/api/agents/'+agent+'/skills'
    cases=[dict(Path=p,User=user,Query=query,Headers={},SQL=sql) for p,user,query,sql in [
        (path,M,'workspace_slug=fixture',''),(path,U,'workspace_slug=fixture',''),
        (path,X,'workspace_slug=fixture',''),('/api/agents/bad/skills',M,'workspace_slug=fixture',''),
        (path,M,'',''),(path,M,'workspace_id=nope',''),
        (path,M,'workspace_slug=fixture',"UPDATE agent SET owner_id=NULL"),
        (path,U,'workspace_slug=fixture',"UPDATE agent SET kind='system'"),
        (path,U,'workspace_slug=fixture',"UPDATE agent SET kind='user'"),
        (path,U,'workspace_slug=fixture',"UPDATE skill SET config='[1,true,null]'"),
        (path,U,'workspace_slug=fixture',"UPDATE skill SET config='{\"a\":1e999,\"b\":-0.0,\"c\":9007199254740993}'"),
        (path,U,'workspace_slug=fixture',"DELETE FROM agent_skill"),
        (path,U,'workspace_slug=fixture',"ALTER TABLE skill RENAME TO fixture_missing_skill")]]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_agent_skills"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cd /work && go build -mod=readonly -p=4 -o /out/agent-skills-oracle ./parity'])
    go=[]
    def observe(container):
        result=command(['docker','run','--rm','--platform','linux/amd64','--network',container.removesuffix('-db'),
            '-i','-e',f'DATABASE_URL=postgres://postgres@{container}:5432/parity?sslmode=disable',
            '-v',f'{binaries}:/out:ro',
            'sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0','/out/agent-skills-oracle'],
            input=json.dumps(dict(Seeds=pg_seeds,Cases=cases)))
        go.extend(json.loads(result.stdout))
        return go
    python=[]
    with tempfile.TemporaryDirectory(prefix='workpal-agent-skills-') as tmp:
        export_schema(Path(tmp)/'schema.json',observe)
        settings=Settings(database_url='sqlite:///'+tmp+'/fixture.sqlite',redis_url='redis://127.0.0.1:1',auth_secret=SECRET)
        migrate(settings)
        app=create_app(settings)
        with TestClient(app) as client:
            with app.state.database.transaction() as session:
                for sql in common:
                    sql=sql.replace('INTO "user"','INTO users').replace('INTO workspace(','INTO workspaces(').replace('INTO member(','INTO members(')
                    session.connection().exec_driver_sql(sql)
            for case in cases:
                if case['SQL']:
                    with app.state.database.transaction() as session:
                        if case['SQL'].startswith('ALTER TABLE activity_log'):
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
    sources=['server/go/internal/handler/skill.go','server/go/pkg/db/queries/skill.sql','server/go/internal/handler/handler.go',
        'server/go/internal/middleware/workspace.go','server/tests/parity/go_agent_skills/main.go',
        'server/src/workpal_backend/agents/skills.py','server/migrations/versions/0018_skill.py','server/src/workpal_backend/infrastructure/go_json_value.py']
    evidence=dict(source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},scope='Agent skill summary handler + workspace middleware status/body and audit fields; actual PostgreSQL/SQLite. UUIDv7 audit IDs and timestamps nondeterministic and excluded; full auth/task/CloudFront/transport not compared.',
        fixtures=cases,pg_seed=pg_seeds,go=go,python=python,mismatches=mismatches,
        binary_sha256=hashlib.sha256((binaries/'agent-skills-oracle').read_bytes()).hexdigest())
    Path(output).write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps(dict(cases=len(cases),mismatches=mismatches)))
    return bool(mismatches)

if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
