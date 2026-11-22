"""Compare selected persistence constraints against a fresh migrated Go database."""
from pathlib import Path
import json
import hashlib
import subprocess
import sys
import tempfile
from export_go_schema import run as export_schema
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from workpal_backend.config import Settings
from workpal_backend.infrastructure.database import Database,migrate
U='10000000-0000-4000-8000-000000000001'
W='10000000-0000-4000-8000-000000000002'
R='10000000-0000-4000-8000-000000000003'
A='10000000-0000-4000-8000-000000000004'
runtime=f"INSERT INTO agent_runtime(id,workspace_id,name,runtime_mode,provider,daemon_id) VALUES ('{R}','{W}','Runtime','local','claude-code','daemon')"
agent=f"INSERT INTO agent(id,workspace_id,name,runtime_mode,runtime_id,owner_id,system_key) VALUES ('{A}','{W}','Agent','local','{R}','{U}','fixture')"
cases=[dict(name='valid-defaults',sql=[])]
for table,column,values in [
    ('agent','status',["'online'","'working'"]),
    ('agent','permission_mode',["'workspace'","'public_to'"]),
    ('agent','kind',["'fake'","'system'"]),
    ('agent','description',["'"+'x'*256+"'"]),
    ('agent','conversation_starters',["'{}'","'[1,2,3,4]'","'[1,2,3]'"]),
    ('agent','runtime_config',["'not-json'","'null'"]),
    ('agent','max_concurrent_tasks',['2147483648','-2147483649','-1','0']),
    ('agent_runtime','visibility',["'workspace'","'public'"]),
    ('agent_runtime','status',["'working'","'online'"]),
    ('agent_runtime','max_concurrent_tasks',['2147483648','NULL']),
]:
    for value in values:cases.append(dict(name=table+'.'+column+'='+value[:20],sql=[f'UPDATE {table} SET {column}={value}']))
cases += [
 dict(name='runtime-delete-restrict',sql=[f"DELETE FROM agent_runtime WHERE id='{R}'"]),
 dict(name='agent-name-unique',sql=[f"INSERT INTO agent(workspace_id,name,runtime_mode) VALUES ('{W}','Agent','local')"]),
 dict(name='daemon-provider-unique',sql=[f"INSERT INTO agent_runtime(workspace_id,name,runtime_mode,provider,daemon_id) VALUES ('{W}','Another','local','claude-code','daemon')"]),
 dict(name='system-identity-unique',sql=[f"INSERT INTO agent(workspace_id,name,runtime_mode,runtime_id,owner_id,system_key) VALUES ('{W}','Other','local','{R}','{U}','fixture')"]),
 dict(name='runtime-profile-allows-other',sql=[f"INSERT INTO agent_runtime(workspace_id,name,runtime_mode,provider,daemon_id,profile_id) VALUES ('{W}','Another','local','claude-code','daemon','{A}')"]),
]


def run(output):
    go=[]
    def observe(container):
        prefix=[f"""INSERT INTO "user"(id,name,email) VALUES ('{U}','Fixture','fixture@example.com')""",
                f"INSERT INTO workspace(id,name,slug) VALUES ('{W}','Fixture','fixture')",runtime,agent]
        for case in cases:
            sql='BEGIN;\n'+';\n'.join(prefix+case['sql'])+';\nROLLBACK;'
            result=subprocess.run(['docker','exec','-i',container,'psql','-X','-q','-U','postgres',
                '-d','parity','-v','ON_ERROR_STOP=1'],input=sql,text=True,capture_output=True)
            go.append(dict(accepted=result.returncode==0,exit_code=result.returncode,
                           error=result.stderr.strip()))
        return go
    with tempfile.TemporaryDirectory(prefix='workpal-agent-schema-') as tmp:
        export_schema(Path(tmp)/'schema.json',observe)
        catalog=json.loads((Path(tmp)/'schema.json').read_text())
        if not go[0]['accepted']:
            raise RuntimeError('PostgreSQL fixture setup failed: '+go[0]['error'])
        settings=Settings(database_url='sqlite:///'+tmp+'/fixture.sqlite',redis_url='redis://127.0.0.1:1')
        migrate(settings)
        db=Database(settings)
        python=[]
        prefix=[f"INSERT INTO users(id,name,email,created_at,updated_at) VALUES ('{U}','Fixture','fixture@example.com','2026-01-01','2026-01-01')",
            f"INSERT INTO workspaces(id,name,slug,issue_prefix,created_at,updated_at) VALUES ('{W}','Fixture','fixture','FX','2026-01-01','2026-01-01')",runtime,agent]
        try:
            for case in cases:
                with db.engine.connect() as conn:
                    transaction=conn.begin()
                    try:
                        for sql in prefix+case['sql']:conn.execute(text(sql))
                        python.append(dict(accepted=True,error=''))
                    except DBAPIError as exc:
                        python.append(dict(accepted=False,error=str(exc.orig)))
                    finally:transaction.rollback()
        finally:db.close()
    if not python[0]['accepted']:
        raise RuntimeError('SQLite fixture setup failed: '+python[0]['error'])
    if len(go)!=len(python):
        raise RuntimeError('missing observations')
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a['accepted']!=b['accepted']]
    evidence=dict(scope='Selected agent/runtime persistence acceptance/rejection only; not SQLSTATE, value canonicalization, lifecycle, API or full schema equivalence.',
        fixtures=cases,go=go,python=python,mismatches=mismatches,
        migration_exit_code=catalog['migration_exit_code'],
        migrator_sha256=catalog['migrator_sha256'],
        migration_manifest_sha256=hashlib.sha256(json.dumps(catalog['migration_sha256'],sort_keys=True).encode()).hexdigest(),
        python_sources_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [
            'server/migrations/versions/0016_agent_runtime.py','server/src/workpal_backend/infrastructure/sqlite_compat.py',
            'server/src/workpal_backend/infrastructure/database.py','server/migrations/env.py',
            'server/tools/run_agent_schema_parity.py']})
    Path(output).write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps(dict(cases=len(cases),mismatches=mismatches)))
    return bool(mismatches)


if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
