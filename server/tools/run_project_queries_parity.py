"""Compare original project-member SQL on migrated PostgreSQL with Python reads.

SQLite tables here are isolated query fixtures, not application migrations.
"""
from pathlib import Path
import hashlib,json,re,subprocess,sys,tempfile
from export_go_schema import run as export_schema
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from sqlalchemy import create_engine,text
from sqlalchemy.orm import Session
from workpal_backend.projects.queries import ProjectQueries

def uid(i):return f'00000000-0000-0000-0000-{i:012x}'
W,OTHER,P,P2,U,V=[uid(i) for i in range(1,7)]
SOURCE=ROOT/'server/go/pkg/db/queries/project_member.sql'
source=SOURCE.read_text()
NAMES=['ListPrivateProjectIDs','ListHiddenProjectIDsForUser','ListPrivateProjectAudience']
def query(name):
    body=source.split('-- name: '+name+' :many\n',1)[1].split('-- name:',1)[0].strip()
    return body.replace('$1',"'"+W+"'").replace("sqlc.arg('workspace_id')","'"+W+"'").replace("sqlc.arg('user_id')","'"+U+"'").rstrip(';')
CASES=[[],[f"INSERT INTO project_member(workspace_id,project_id,user_id) VALUES ('{W}','{P}','{U}')"],
 [f"INSERT INTO project_member(workspace_id,project_id,user_id) VALUES ('{OTHER}','{P}','{U}'),('{W}','{P}','{V}')"],
 [f"UPDATE project SET visibility='workspace' WHERE id='{P}'"],
 [f"UPDATE project SET workspace_id='{OTHER}' WHERE id='{P}'"],
 [f"INSERT INTO project_member(workspace_id,project_id,user_id) VALUES ('{W}','{P2}','{U}')",f"DELETE FROM project_member WHERE user_id='{U}'"]]

def ordered(rows):return sorted(rows,key=lambda r:tuple('' if value is None else value for value in r))
def run(output):
    go=[]
    def observe(container):
        prefix=[f"INSERT INTO workspace(id,name,slug) VALUES ('{W}','Fixture','fixture'),('{OTHER}','Other','other')",
            f"INSERT INTO project(id,workspace_id,title,visibility) VALUES ('{P}','{W}','Private','private'),('{P2}','{W}','Empty','private')"]
        for case in CASES:
            observations=[]
            for name in NAMES:
                sql='BEGIN;\n'+';\n'.join(prefix+case)+';\nSELECT COALESCE(json_agg(row_to_json(q)),\'[]\'::json) FROM (\n'+query(name)+'\n) q;\nROLLBACK;'
                result=subprocess.run(['docker','exec','-i',container,'psql','-X','-q','-t','-A','-U','postgres','-d','parity','-v','ON_ERROR_STOP=1'],input=sql,text=True,capture_output=True)
                if result.returncode:raise RuntimeError(result.stderr)
                rows=json.loads(result.stdout.strip())
                observations.append(ordered([[row['project_id'],row['user_id']] if name==NAMES[2] else [row['id']] for row in rows]))
            go.append(observations)
        return go
    with tempfile.TemporaryDirectory(prefix='workpal-project-queries-') as tmp:
        export_schema(Path(tmp)/'schema.json',observe)
        catalog=json.loads((Path(tmp)/'schema.json').read_text())
    engine=create_engine('sqlite://')
    with engine.begin() as c:
        c.execute(text('CREATE TABLE project(id TEXT PRIMARY KEY,workspace_id TEXT,title TEXT,visibility TEXT)'))
        c.execute(text('CREATE TABLE project_member(workspace_id TEXT,project_id TEXT,user_id TEXT)'))
    python=[]
    try:
        for case in CASES:
            with engine.connect() as conn:
                transaction=conn.begin()
                conn.execute(text(f"INSERT INTO project VALUES ('{P}','{W}','Private','private'),('{P2}','{W}','Empty','private')"))
                for sql in case:conn.execute(text(sql))
                with Session(bind=conn) as session:
                    q=ProjectQueries(session)
                    python.append([ordered([[v] for v in q.list_private_project_ids(W)]),ordered([[v] for v in q.list_hidden_project_ids(W,U)]),ordered([list(row) for row in q.list_private_project_audience(W)])])
                transaction.rollback()
    finally:engine.dispose()
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/pkg/db/queries/project_member.sql','server/src/workpal_backend/projects/queries.py']
    Path(output).write_text(json.dumps(dict(scope='Original three project visibility SQL queries on actual Go-migrated PostgreSQL versus Python SQL adapter on isolated SQLite fixture tables. Unordered SQL results compared as multisets. Does not certify schema/migrations, concurrency, remaining queries, or live routes.',queries=NAMES,cases=CASES,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(CASES),observations=len(CASES)*len(NAMES),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
