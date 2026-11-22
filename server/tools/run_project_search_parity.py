"""Actual PostgreSQL project triggers and snapshots versus isolated SQLite."""
from pathlib import Path
import hashlib
import json
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
from workpal_backend.infrastructure.snapshots import parse_snapshot,visible
U='10000000-0000-4000-8000-000000000001'
W='10000000-0000-4000-8000-000000000002'
P='10000000-0000-4000-8000-000000000003'
INSERT=f"INSERT INTO project(id,workspace_id,title) VALUES ('{P}','{W}','Fixture')"
FIELDS='id,workspace_id,title,description,icon,status,lead_type,lead_id,priority,start_date,due_date,workflow_id,creator_type,creator_id,visibility,archived_at,archived_by_type,archived_by_id,folder_id'
cases=[dict(name='defaults',sql=[])]
for column,values in [('status',["'cancelled'","'archived'"]),('priority',["'high'","'unknown'"]),
                      ('lead_type',["'agent'","'system'"]),('visibility',["'custom-value'"]),('title',['NULL',"''"])]:
    for value in values:cases.append(dict(name=column+'='+value,sql=[f'UPDATE project SET {column}={value}']))
cases += [dict(name='delete-tombstone',sql=['DELETE FROM project']),
          dict(name='suppress-teardown',sql=["SET LOCAL workpal.workspace_teardown = 'on'",'DELETE FROM project']),
          dict(name='savepoint-rollback',sql=['DELETE FROM project','SAVEPOINT nested',INSERT,'ROLLBACK TO nested',INSERT])]
snapshots=['3:3:','3:6:4','3:6:5,4','3:6:4,4','0:0:','0:1:','5:3:','3:6:2','3:6:6',' 3:3:','3:3: ',
           '03:06:04','3:18446744073709551615:4','3:18446744073709551616:','invalid']

snapshots += ['+3:6:4','3: 6:4','3:6: 4','3 :6:4','3:6:4 ','3:6:4,','1:1:','2:2:',
              '-1:-1:','3:-1:4','3:6:+4','3:6:-0','3:6:0004','3:6:4,3','3:6:3,3','3:6:5,5','3:6:4,5','\t3:6:4']


def run(output):
    pg=[];pg_snap=[]
    def observe(container):
        def sqlrun(sql):
            return subprocess.run(['docker','exec','-i',container,'psql','-X','-q','-A','-t','-U','postgres','-d','parity','-v','ON_ERROR_STOP=1'],input=sql,text=True,capture_output=True)
        prefix=[f"""INSERT INTO "user"(id,name,email) VALUES ('{U}','Fixture','fixture@example.com')""",f"INSERT INTO workspace(id,name,slug) VALUES ('{W}','Fixture','fixture')",INSERT]
        state=f"""SELECT json_build_object(
            'projects',(SELECT COALESCE(json_agg(r),'[]') FROM (SELECT {FIELDS} FROM project ORDER BY id) r),
            'changes',(SELECT COALESCE(json_agg(r),'[]') FROM (SELECT entity_type,entity_id,workspace_id,
                change_xid=pg_current_xact_id() AS own_xid,changed_at=now() AS same_clock FROM search_index_change ORDER BY entity_type,entity_id) r),
            'own_visible',pg_visible_in_snapshot(pg_current_xact_id(),pg_current_snapshot()));"""
        for case in cases:
            result=sqlrun('BEGIN;\n'+';\n'.join(prefix+case['sql'])+';\n'+state+'\nROLLBACK;')
            pg.append(dict(accepted=result.returncode==0,state=json.loads(result.stdout) if result.returncode==0 else None,error=result.stderr.strip()))
        for snap in snapshots:
            literal="'"+snap.replace("'","''")+"'::pg_snapshot"
            result=sqlrun(f"SELECT json_build_object('canonical',({literal})::text,'visible',pg_visible_in_snapshot('4'::xid8,{literal}));")
            pg_snap.append(dict(accepted=result.returncode==0,state=json.loads(result.stdout) if result.returncode==0 else None))
        return pg
    python=[];py_snap=[]
    with tempfile.TemporaryDirectory(prefix='workpal-project-search-') as tmp:
        export_schema(Path(tmp)/'schema.json',observe)
        if not pg[0]['accepted']:raise RuntimeError(pg[0]['error'])
        settings=Settings(database_url='sqlite:///'+tmp+'/fixture.sqlite',redis_url='redis://127.0.0.1:1')
        migrate(settings);database=Database(settings)
        prefix=[f"INSERT INTO users(id,name,email,created_at,updated_at) VALUES ('{U}','Fixture','fixture@example.com','2026-01-01','2026-01-01')",f"INSERT INTO workspaces(id,name,slug,issue_prefix,created_at,updated_at) VALUES ('{W}','Fixture','fixture','FX','2026-01-01','2026-01-01')",INSERT]
        try:
            for case in cases:
                with database.engine.connect() as conn:
                    transaction=conn.begin()
                    try:
                        for sql in prefix+case['sql']:
                            if sql.startswith('SET LOCAL'):conn.info['transaction_settings']['workpal.workspace_teardown']='on'
                            else:conn.execute(text(sql))
                        projects=[dict(r) for r in conn.execute(text(f'SELECT {FIELDS} FROM project ORDER BY id')).mappings()]
                        changes=[dict(r) for r in conn.execute(text('SELECT entity_type,entity_id,workspace_id,change_xid=workpal_xid() AS own_xid,changed_at=workpal_now() AS same_clock FROM search_index_change ORDER BY entity_type,entity_id')).mappings()]
                        for row in changes:
                            row['own_xid']=bool(row['own_xid']);row['same_clock']=bool(row['same_clock'])
                        own=bool(conn.scalar(text('SELECT workpal_visible_in_snapshot(workpal_xid(),workpal_current_snapshot())')))
                        python.append(dict(accepted=True,state=dict(projects=projects,changes=changes,own_visible=own),error=''))
                    except DBAPIError as exc:python.append(dict(accepted=False,state=None,error=str(exc.orig)))
                    finally:transaction.rollback()
        finally:database.close()
    for snap in snapshots:
        try:
            low,high,active=parse_snapshot(snap)
            state=dict(canonical=f'{low}:{high}:'+','.join(str(x) for x in sorted(active)),visible=bool(visible(4,snap)))
            py_snap.append(dict(accepted=True,state=state))
        except ValueError:py_snap.append(dict(accepted=False,state=None))
    if len(pg)!=len(python) or len(pg_snap)!=len(py_snap):raise RuntimeError('missing observations')
    mismatches=[i for i,(a,b) in enumerate(zip(pg,python)) if (a['accepted'],a['state'])!=(b['accepted'],b['state'])]
    snapshot_mismatches=[i for i,(a,b) in enumerate(zip(pg_snap,py_snap)) if a!=b]
    sources=['server/go/migrations/561_search_index_change.up.sql','server/migrations/versions/0020_project_search.py','server/src/workpal_backend/infrastructure/snapshots.py','server/src/workpal_backend/infrastructure/sqlite_compat.py']
    Path(output).write_text(json.dumps(dict(scope='Project constraints and trigger state; transaction IDs/timestamps compared relationally. Snapshot grammar/visibility fixtures. Full concurrency, retention and HTTP gates remain pending.',cases=cases,go=pg,python=python,snapshots=snapshots,go_snapshots=pg_snap,python_snapshots=py_snap,mismatches=mismatches,snapshot_mismatches=snapshot_mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(cases),mismatches=mismatches,snapshot_cases=len(snapshots),snapshot_mismatches=snapshot_mismatches)))
    return bool(mismatches or snapshot_mismatches)

if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
