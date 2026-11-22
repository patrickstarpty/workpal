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
C='10000000-0000-4000-8000-000000000005'
chat=f"INSERT INTO chat_session(id,workspace_id,agent_id,creator_id,runtime_id) VALUES ('{C}','{W}','{A}','{U}','{R}')"
cases=[dict(name='valid-defaults',sql=[])]
for column,values in [
    ('status',["'deleted'","'archived'",'NULL']),
    ('title',['NULL',"''"]),('is_agent_intro',['NULL','true','false']),
    ('agent_id',["'00000000-0000-4000-8000-000000000001'"]),
    ('creator_id',["'00000000-0000-4000-8000-000000000001'"]),
    ('workspace_id',["'00000000-0000-4000-8000-000000000001'"]),
    ('runtime_id',["'00000000-0000-4000-8000-000000000001'",'NULL']),
    ('project_id',["'00000000-0000-4000-8000-000000000001'"]),
]:
    for value in values:cases.append(dict(name='chat_session.'+column+'='+value,sql=[f'UPDATE chat_session SET {column}={value}']))
cases += [dict(name='delete-agent-cascade',sql=[f"DELETE FROM agent WHERE id='{A}'"]),
          dict(name='delete-runtime-unbind',sql=['UPDATE agent SET runtime_id=NULL',f"DELETE FROM agent_runtime WHERE id='{R}'"])]


STATE_SQL="""SELECT id,workspace_id,agent_id,creator_id,title,session_id,work_dir,status,
    runtime_id,is_agent_intro,project_id,unread_since,pinned_at,explicitly_created_at,
    (created_at=updated_at AND updated_at=last_read_at) AS default_clock_match
    FROM chat_session ORDER BY id"""


def run(output):
    go=[]
    def observe(container):
        prefix=[f"""INSERT INTO "user"(id,name,email) VALUES ('{U}','Fixture','fixture@example.com')""",
                f"INSERT INTO workspace(id,name,slug) VALUES ('{W}','Fixture','fixture')",runtime,agent,chat]
        for case in cases:
            sql='BEGIN;\n'+';\n'.join(prefix+case['sql'])+";\nSELECT COALESCE(json_agg(r), '[]') FROM ("+STATE_SQL+") r;\nROLLBACK;"
            result=subprocess.run(['docker','exec','-i',container,'psql','-X','-q','-A','-t','-U','postgres',
                '-d','parity','-v','ON_ERROR_STOP=1'],input=sql,text=True,capture_output=True)
            go.append(dict(accepted=result.returncode==0,exit_code=result.returncode,
                           error=result.stderr.strip(),state=json.loads(result.stdout) if result.returncode==0 else None))
        return go
    with tempfile.TemporaryDirectory(prefix='workpal-chat-session-schema-') as tmp:
        export_schema(Path(tmp)/'schema.json',observe)
        catalog=json.loads((Path(tmp)/'schema.json').read_text())
        if not go[0]['accepted']:
            raise RuntimeError('PostgreSQL fixture setup failed: '+go[0]['error'])
        settings=Settings(database_url='sqlite:///'+tmp+'/fixture.sqlite',redis_url='redis://127.0.0.1:1')
        migrate(settings)
        db=Database(settings)
        python=[]
        prefix=[f"INSERT INTO users(id,name,email,created_at,updated_at) VALUES ('{U}','Fixture','fixture@example.com','2026-01-01','2026-01-01')",
            f"INSERT INTO workspaces(id,name,slug,issue_prefix,created_at,updated_at) VALUES ('{W}','Fixture','fixture','FX','2026-01-01','2026-01-01')",runtime,agent,chat]
        try:
            for case in cases:
                with db.engine.connect() as conn:
                    transaction=conn.begin()
                    try:
                        for sql in prefix+case['sql']:conn.execute(text(sql))
                        state=[dict(row) for row in conn.execute(text(STATE_SQL)).mappings()]
                        for row in state:
                            row['is_agent_intro']=bool(row['is_agent_intro'])
                            row['default_clock_match']=bool(row['default_clock_match'])
                        python.append(dict(accepted=True,error='',state=state))
                    except DBAPIError as exc:
                        python.append(dict(accepted=False,error=str(exc.orig),state=None))
                    finally:transaction.rollback()
        finally:db.close()
    if not python[0]['accepted']:
        raise RuntimeError('SQLite fixture setup failed: '+python[0]['error'])
    if len(go)!=len(python):
        raise RuntimeError('missing observations')
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a['accepted']!=b['accepted'] or a['state']!=b['state']]
    evidence=dict(scope='Selected canonical chat_session persistence acceptance/rejection plus projected defaults and cascade/unbind row state; timestamps compared by transaction equality only. Not SQLSTATE, full type domains, API or full schema equivalence.',
        fixtures=cases,go=go,python=python,mismatches=mismatches,
        migration_exit_code=catalog['migration_exit_code'],
        migrator_sha256=catalog['migrator_sha256'],
        migration_manifest_sha256=hashlib.sha256(json.dumps(catalog['migration_sha256'],sort_keys=True).encode()).hexdigest(),
        python_sources_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [
            'server/migrations/versions/0019_chat_session.py','server/src/workpal_backend/infrastructure/sqlite_compat.py',
            'server/src/workpal_backend/infrastructure/database.py','server/migrations/env.py',
            'server/tools/run_chat_session_schema_parity.py']})
    Path(output).write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps(dict(cases=len(cases),mismatches=mismatches)))
    return bool(mismatches)


if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
