"""Original paired-unnest membership SQL on Go-migrated isolated PostgreSQL."""
from pathlib import Path
import hashlib,json,subprocess,sys,tempfile,uuid
from export_go_schema import run as export_schema
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from sqlalchemy import create_engine,text
from sqlalchemy.orm import Session
from workpal_backend.realtime.membership_queries import MembershipQueries
W='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';V='bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
U='11111111-1111-1111-1111-111111111111';X='22222222-2222-2222-2222-222222222222'
CASES=[[],[(W,U)],[(W,X),(V,U)],[(W,U),(V,X)],[(W,U),(W,U)],[(W.upper(),U.replace('-',''))],[(V,X),(W,X),(W,U)]]

def run(output):
    source=(ROOT/'server/go/pkg/db/queries/member.sql').read_text()
    query=source.split('-- name: GetRealtimeMemberships :many\n',1)[1].split('-- name:',1)[0].strip().rstrip(';')
    go=[]
    def observe(container):
        seed=f'''INSERT INTO "user"(id,name,email) VALUES ('{U}','U','u@parity.invalid'),('{X}','X','x@parity.invalid');
INSERT INTO workspace(id,name,slug) VALUES ('{W}','W','w'),('{V}','V','v');
INSERT INTO member(workspace_id,user_id,role) VALUES ('{W}','{U}','member'),('{V}','{X}','owner');'''
        for deleted in [False,True]:
            for case in CASES:
                def array(index):return 'ARRAY['+','.join("'"+identity[index]+"'" for identity in case)+']::uuid[]'
                body=query.replace('sqlc.arg(user_ids)::uuid[]',array(1)).replace('sqlc.arg(workspace_ids)::uuid[]',array(0))
                sql='BEGIN;\n'+seed+(f"DELETE FROM member WHERE user_id='{U}';" if deleted else '')+"\nSELECT COALESCE(json_agg(row_to_json(q)),'[]'::json) FROM ("+body+') q;\nROLLBACK;'
                result=subprocess.run(['docker','exec','-i',container,'psql','-X','-q','-t','-A','-U','postgres','-d','parity','-v','ON_ERROR_STOP=1'],input=sql,text=True,capture_output=True)
                if result.returncode:raise RuntimeError(result.stderr)
                rows=json.loads(result.stdout.strip());present={(r['workspace_id'],r['user_id']) for r in rows}
                go.append(sorted([list(pair) for pair in set(case) if tuple(str(uuid.UUID(i)) for i in pair) in present]))
        return go
    with tempfile.TemporaryDirectory(prefix='workpal-membership-query-') as tmp:
        export_schema(Path(tmp)/'schema.json',observe)
    engine=create_engine('sqlite://');python=[]
    try:
        with engine.begin() as conn:conn.execute(text('CREATE TABLE members(workspace_id TEXT,user_id TEXT)'))
        for deleted in [False,True]:
            for case in CASES:
                with engine.connect() as conn:
                    transaction=conn.begin()
                    conn.execute(text('INSERT INTO members VALUES (:w,:u),(:v,:x)'),dict(w=W,u=U,v=V,x=X))
                    if deleted:conn.execute(text('DELETE FROM members WHERE user_id=:u'),dict(u=U))
                    with Session(bind=conn) as session:python.append(sorted([list(pair) for pair in MembershipQueries(session).members(case)]))
                    transaction.rollback()
    finally:engine.dispose()
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/pkg/db/queries/member.sql','server/src/workpal_backend/realtime/membership_queries.py','server/src/workpal_backend/infrastructure/go_uuid.py']
    Path(output).write_text(json.dumps(dict(scope='Original paired membership SQL executed on actual Go-migrated PostgreSQL vs Python SQL adapter on isolated SQLite fixtures, membership result keys compared as sets. Does not execute Go router membershipChecker.Members, certify invalid UUID errors, DB concurrency/cancellation/schema equivalence.',cases=CASES,deleted_states=[False,True],go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(observations=len(go),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
