"""Compare a second independent project writer while the first remains open."""
from pathlib import Path
import json
import selectors
import subprocess
import sys
import tempfile
from export_go_schema import run as export_schema
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from workpal_backend.config import Settings
from workpal_backend.infrastructure.database import Database,migrate
W='20000000-0000-4000-8000-000000000001'
A='30000000-0000-4000-8000-000000000001'
B='30000000-0000-4000-8000-000000000002'


def run(output):
    observed={}
    def observe(container):
        cmd=['docker','exec','-i',container,'psql','-X','-q','-A','-t','-U','postgres','-d','parity','-v','ON_ERROR_STOP=1']
        seed=f"INSERT INTO workspace(id,name,slug) VALUES ('{W}','Fixture','fixture');"
        for pid in [A,B]:seed+=f"INSERT INTO project(id,workspace_id,title) VALUES ('{pid}','{W}','Before');"
        subprocess.run(cmd,input=seed,text=True,capture_output=True,check=True)
        first=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
        try:
            first.stdin.write(f"BEGIN; UPDATE project SET title='Writer A' WHERE id='{A}'; SELECT 'A_READY';\n");first.stdin.flush()
            with selectors.DefaultSelector() as selector:
                selector.register(first.stdout,selectors.EVENT_READ)
                if not selector.select(10):raise RuntimeError('PostgreSQL first writer did not become ready')
                if first.stdout.readline().strip()!='A_READY':raise RuntimeError('PostgreSQL first writer setup failed')
            second=subprocess.run(cmd,input=f"BEGIN; SET LOCAL statement_timeout='1000ms'; UPDATE project SET title='Writer B' WHERE id='{B}'; SELECT 'B_UPDATED'; ROLLBACK;",text=True,capture_output=True,timeout=10)
            observed['postgresql']=dict(first_writer_open=first.poll() is None,second_writer_updated=second.returncode==0 and 'B_UPDATED' in second.stdout,error=second.stderr.strip())
            first.stdin.write('ROLLBACK;\n\\q\n');first.stdin.flush();first.communicate(timeout=10)
        finally:
            if first.poll() is None:first.kill();first.communicate()
        return observed
    with tempfile.TemporaryDirectory(prefix='workpal-writer-probe-') as tmp:
        export_schema(Path(tmp)/'schema.json',observe)
        settings=Settings(database_url='sqlite:///'+tmp+'/fixture.sqlite',redis_url='redis://127.0.0.1:1',busy_timeout_ms=1000)
        migrate(settings);db=Database(settings)
        try:
            with db.transaction() as session:
                session.execute(text("INSERT INTO workspaces(id,name,slug,issue_prefix,created_at,updated_at) VALUES (:id,'Fixture','fixture','FX','2026-01-01','2026-01-01')"),dict(id=W))
                for pid in [A,B]:session.execute(text("INSERT INTO project(id,workspace_id,title) VALUES (:id,:ws,'Before')"),dict(id=pid,ws=W))
            with db.engine.connect() as first,db.engine.connect() as second:
                tx1=first.begin();tx2=second.begin()
                try:
                    first.execute(text("UPDATE project SET title='Writer A' WHERE id=:id"),dict(id=A))
                    try:
                        second.execute(text("UPDATE project SET title='Writer B' WHERE id=:id"),dict(id=B))
                        observed['sqlite']=dict(first_writer_open=tx1.is_active,second_writer_updated=True,error='')
                    except OperationalError as exc:
                        observed['sqlite']=dict(first_writer_open=tx1.is_active,second_writer_updated=False,error=str(exc.orig))
                finally:tx2.rollback();tx1.rollback()
        finally:db.close()
    if not observed['postgresql']['first_writer_open'] or not observed['sqlite']['first_writer_open']:raise RuntimeError('invalid schedule')
    observed['scope']='Two independent project row updates under one-second statement/busy timeout, first writer held open; isolated fresh schemas, actual Go project search triggers on PostgreSQL.'
    observed['equivalent']=observed['postgresql']['second_writer_updated']==observed['sqlite']['second_writer_updated']
    Path(output).write_text(json.dumps(observed,indent=2)+'\n')
    print(json.dumps(observed))

if __name__=='__main__':run(sys.argv[1])
