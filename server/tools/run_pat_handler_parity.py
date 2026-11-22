"""Execute actual Go PAT handlers/Postgres and Python handlers/SQLite.

Identity is fixture-injected on both sides. This is not middleware evidence.
The PostgreSQL fixture uses the original PAT migration; unrelated tables are
not migrated. No production DB, network service, model or user secret is used.
"""
from pathlib import Path
from datetime import datetime
import hashlib
import json
import subprocess
import sys
import tempfile
import time
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import text
from workpal_backend.app import create_app
from workpal_backend.config import Settings
from workpal_backend.infrastructure.database import migrate
from workpal_backend.auth.dependencies import Principal, require_principal

OWNER='11111111-1111-4111-8111-111111111111'

def command(args, **kwargs):
    return subprocess.run(args,check=True,capture_output=True,text=True,**kwargs)


def run(output):
    fixtures=ROOT/'server/tests/parity/cases/pat_handlers.json'
    cases=json.loads(fixtures.read_text())
    seeds=json.loads((ROOT/'server/tests/parity/cases/pat_seed.json').read_text())
    run_id=uuid4().hex[:12]
    network='workpal-pat-parity-'+run_id
    container=network+'-db'
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none',
        '-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT / "server/tests/parity/go_pat"}:/harness:ro',
        '-v',f'{binaries}:/out','-v','workpal-go-parity-modcache:/go/pkg/mod',
        '-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cd /work && go build -mod=readonly -p=4 -o /out/pat-oracle ./parity'])
    command(['docker','network','create','--internal',network])
    try:
        command(['docker','run','-d','--name',container,'--network',network,'--tmpfs','/var/lib/postgresql/data',
            '-e','POSTGRES_HOST_AUTH_METHOD=trust','-e','POSTGRES_DB=parity','postgres:17-alpine'])
        for _ in range(100):
            probe=subprocess.run(['docker','exec',container,'pg_isready','-U','postgres','-d','parity'],capture_output=True)
            if probe.returncode==0:break
            time.sleep(.1)
        else:raise RuntimeError('isolated PostgreSQL did not become ready')
        go_run=command(['docker','run','--rm','--platform','linux/amd64','--network',network,'-i',
            '-e',f'DATABASE_URL=postgres://postgres@{container}:5432/parity?sslmode=disable',
            '-v',f'{reference}:/reference:ro','-v',f'{binaries}:/out:ro',
            'sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0','/out/pat-oracle'],input=json.dumps({'cases':cases,'seeds':seeds}))
        go=json.loads(go_run.stdout)
    finally:
        subprocess.run(['docker','rm','-f',container],capture_output=True)
        command(['docker','network','rm',network])
    python=[]
    with tempfile.TemporaryDirectory(prefix='workpal-pat-parity-') as tmp:
        settings=Settings(database_url='sqlite:///'+tmp+'/db.sqlite',redis_url='redis://127.0.0.1:1',upload_dir=Path(tmp)/'uploads')
        migrate(settings)
        app=create_app(settings)
        def identity(request: Request):
            return Principal(OWNER,request.headers.get('x-fixture-actor') or 'session')
        app.dependency_overrides[require_principal]=identity
        with TestClient(app) as client:
            from workpal_backend.auth.models import users
            from workpal_backend.auth.personal_tokens import pats
            with app.state.database.transaction() as session:
                session.execute(users.insert().values(id=OWNER,name='Fixture',email='fixture@example.invalid',created_at='2026-01-01',updated_at='2026-01-01'))
                for seed in seeds:
                    session.execute(pats.insert().values(**{**seed,'created_at':datetime.fromisoformat(seed['created_at']).timestamp(),'expires_at':datetime.fromisoformat(seed['expires_at']).timestamp() if seed.get('expires_at') else None},user_id=OWNER,revoked=False))
            for case in cases:
                response=client.request(case['method'],case['path'],content=case['body'],headers={
                    'x-fixture-actor':case.get('actor',''),'authorization':case.get('authorization','')})
                with app.state.database.transaction() as session:
                    state=[dict(row) for row in session.execute(pats.select().order_by(pats.c.id)).mappings()]
                python.append(dict(status=response.status_code,headers={k:[v] for k,v in response.headers.items()},
                    body=response.json() if response.content else None,wire_body=response.text,
                    state={'tokens':state},events=None,external_calls=None))
    # HTTP field names are case-insensitive; do not discard any header/value.
    for observation in go:
        observation['headers']={k.lower():v for k,v in observation['headers'].items()}
    if len(go)!=len(python):raise RuntimeError('missing observations')
    mismatches=[{'case':i,'channels':[key for key in go[i] if go[i][key]!=python[i][key]]}
        for i in range(len(cases)) if go[i]!=python[i]]
    paths=['server/go/internal/handler/personal_access_token.go','server/go/pkg/db/queries/personal_access_token.sql',
        'server/go/migrations/011_personal_access_tokens.up.sql','server/tests/parity/go_pat/main.go']
    evidence=dict(scope='PAT handler boundary with seeded lifecycle, fixture identity, isolated PostgreSQL/SQLite; not middleware, random issuance or full lifecycle',
        unobserved_channels=['events','external_calls'],
        source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},
        binary_sha256=hashlib.sha256((binaries/'pat-oracle').read_bytes()).hexdigest(),
        fixtures=cases,seeds=seeds,go=go,python=python,mismatches=mismatches,
        normalization=['HTTP header names lowercased; values preserved'],go_exit_code=go_run.returncode)
    Path(output).write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps({'cases':len(cases),'mismatches':mismatches}))
    return bool(mismatches)

if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
