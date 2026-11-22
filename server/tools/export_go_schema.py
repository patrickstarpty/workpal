"""Export fresh reference schema after the real Go migrator; isolated tmpfs only."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import time
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[2]


def command(args, **kwargs):
    return subprocess.run(args,check=True,text=True,capture_output=True,**kwargs)


def run(output, observe=None):
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{binaries}:/out','-v','workpal-go-parity-modcache:/go/pkg/mod',
        '-v','workpal-go-parity-buildcache:/root/.cache/go-build','-e','GOOS=linux',
        '-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work && cp -a /reference/server/go/. /work/ && cd /work && go build -mod=readonly -p=4 -o /out/schema-migrate ./cmd/migrate'])
    network='workpal-schema-'+uuid4().hex[:10]
    container=network+'-db'
    command(['docker','network','create','--internal',network])
    try:
        command(['docker','run','-d','--name',container,'--network',network,
            '--tmpfs','/var/lib/postgresql/data','-e','POSTGRES_HOST_AUTH_METHOD=trust',
            '-e','POSTGRES_DB=parity','postgres:17-alpine'])
        for _ in range(100):
            result=subprocess.run(['docker','exec',container,'pg_isready','-U','postgres','-d','parity'],capture_output=True)
            if result.returncode==0:break
            time.sleep(.1)
        else:raise RuntimeError('isolated PostgreSQL did not become ready')
        migration=command(['docker','run','--rm','--platform','linux/amd64','--network',network,
            '-e',f'DATABASE_URL=postgres://postgres@{container}:5432/parity?sslmode=disable',
            '-v',f'{reference}:/reference:ro','-v',f'{binaries}:/out:ro',
            '-w','/reference/server/go','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
            '/out/schema-migrate','up'])
        Path(output).with_suffix('.migration.log').write_text(migration.stdout+migration.stderr)
        queries={
          'columns':"""SELECT table_name,column_name,ordinal_position,data_type,udt_name,is_nullable,column_default
            FROM information_schema.columns WHERE table_schema='public' ORDER BY table_name,ordinal_position""",
          'constraints':"""SELECT c.relname AS table_name,k.conname AS name,k.contype AS type,
            pg_get_constraintdef(k.oid) AS definition,k.convalidated AS validated
            FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' ORDER BY c.relname,k.conname""",
          'indexes':"""SELECT tablename AS table_name,indexname AS name,indexdef AS definition
            FROM pg_indexes WHERE schemaname='public' ORDER BY tablename,indexname""",
          'triggers':"""SELECT c.relname AS table_name,t.tgname AS name,pg_get_triggerdef(t.oid) AS definition
            FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND NOT t.tgisinternal ORDER BY c.relname,t.tgname""",
          'migrations':'SELECT version FROM schema_migrations ORDER BY version',
        }
        result={}
        for key,query in queries.items():
            raw=command(['docker','exec',container,'psql','-X','-A','-t','-U','postgres','-d','parity',
                '-v','ON_ERROR_STOP=1','-c','SELECT coalesce(json_agg(row_to_json(t)),\'[]\'::json) FROM ('+query+') t']).stdout
            result[key]=json.loads(raw)
        if observe is not None:
            result['observations'] = observe(container)
        paths=sorted((ROOT/'server/go/migrations').glob('*.up.sql'))
        result.update(scope='Fresh isolated PostgreSQL schema after actual Go migrator; not SQLite equivalence evidence',
            migration_exit_code=migration.returncode,
            migration_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
            migrator_sha256=hashlib.sha256((binaries/'schema-migrate').read_bytes()).hexdigest())
        Path(output).write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({key:len(result[key]) for key in queries}))
    finally:
        subprocess.run(['docker','rm','-f',container],capture_output=True)
        subprocess.run(['docker','network','rm',network],capture_output=True)


if __name__=='__main__':run(sys.argv[1])
