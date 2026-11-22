"""Real Auth middleware oracle; compares identity/status/error bytes and headers.

Go httptest omits net/http's transport-added Content-Length on http.Error;
that transport-level header is recorded but not equated to ASGI's explicit
length here. Full socket-level transport parity remains a separate gate.
"""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile
import jwt
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from fastapi import Depends,Response
from fastapi.testclient import TestClient
from workpal_backend.app import create_app
from workpal_backend.config import Settings
from workpal_backend.auth.dependencies import require_principal
from workpal_backend.auth.tokens import csrf_token

SECRET='s'*64  # Public deterministic test key, never read from user configuration.


def run(output, secret=SECRET):
    claims_cases=[{'sub':'user'}, {'sub':'user','iat':9999999999}, {'sub':'user','iat':'ignored'},
        {'sub':'user','exp':0},{'sub':'user','exp':None},{'sub':'user','exp':'4102444800'},
        {'sub':'user','exp':1},{'sub':'user','nbf':4102444800},{'sub':'user','nbf':None},
        {'sub':'user','nbf':0},{'sub':'user','nbf':1.9},{'sub':'user','email':7,'sid':None},
        {}, {'sub':7},{'sub':' \t'}, {'sub':'514492f7-b30f-4147-bd33-c0e8ce5d6d4f'},
        {'sub':'user','email':' PDZZER68@EMBASSYBASE.COM '},{'sub':'user','extra':float('nan')}]
    cases=[dict(method='GET',headers={'Authorization':'Bearer '+jwt.encode(claims,secret,algorithm=alg)})
        for alg in ('HS256','HS384','HS512') for claims in claims_cases]
    cases += [dict(method='GET',headers={}),dict(method='GET',headers={'Authorization':'Bearer invalid'})]
    expired=jwt.encode({'sub':'user','sid':'old','exp':1},secret,algorithm='HS256')
    cases += [dict(method='POST',headers={'Cookie':'workpal_auth='+expired}),
        dict(method='POST',headers={'Cookie':'workpal_auth='+expired,'X-CSRF-Token':csrf_token(secret,'old')})]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    subprocess.run(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_jwt"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cd /work && go build -mod=readonly -p=4 -o /out/jwt-oracle ./parity'],check=True)
    result=subprocess.run(['docker','run','--rm','--platform','linux/amd64','--network','none','-i',
        '-e','JWT_SECRET='+secret,'-v',f'{binaries}:/out:ro',
        'sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0','/out/jwt-oracle'],
        input=json.dumps(cases),text=True,capture_output=True,check=True)
    go=json.loads(result.stdout)
    python=[]
    with tempfile.TemporaryDirectory(prefix='workpal-jwt-oracle-') as tmp:
        app=create_app(Settings(database_url='sqlite:///'+tmp+'/db',auth_secret=secret,redis_url='redis://127.0.0.1:1',upload_dir=Path(tmp)/'uploads'))
        @app.get('/fixture/identity')
        @app.post('/fixture/identity')
        def identity(principal=Depends(require_principal)):
            return Response(status_code=204,headers={'X-Fixture-User':principal.user_id})
        with TestClient(app) as client:
            for case in cases:
                response=client.request(case['method'],'/fixture/identity',headers=case['headers'])
                python.append(dict(status=response.status_code,body=response.text,headers={k:[v] for k,v in response.headers.items()},user_id=response.headers.get('x-fixture-user','')))
    for row in go:row['headers']={k.lower():v for k,v in row['headers'].items()}
    compared_headers=['content-type','x-content-type-options','x-fixture-user']
    mismatches=[]
    if len(go)!=len(python):raise RuntimeError('missing observations')
    for i,(left,right) in enumerate(zip(go,python)):
        keys=[k for k in ('status','body','user_id') if left[k]!=right[k]]
        keys += ['headers.'+k for k in compared_headers if left['headers'].get(k)!=right['headers'].get(k)]
        if keys:mismatches.append({'case':i,'channels':keys})
    sources=['server/go/internal/middleware/auth.go','server/go/internal/auth/cookie.go','server/go/internal/auth/temporary_disabled_users.go','server/tests/parity/go_jwt/main.go']
    evidence=dict(scope='JWT Auth status/identity/error body and listed explicit headers; no DB, renewals, or full transport claim',
        compared_headers=compared_headers,unverified=['Content-Length transport framing','other response headers','renewal cookies','PAT/task/cloud branches'],
        test_only=True,fixtures=cases,go=go,python=python,mismatches=mismatches,go_exit_code=result.returncode,
        source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},
        binary_sha256=hashlib.sha256((binaries/'jwt-oracle').read_bytes()).hexdigest())
    Path(output).write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps({'cases':len(cases),'mismatches':mismatches}))
    return bool(mismatches)

if __name__=='__main__':raise SystemExit(run(sys.argv[1],sys.argv[2] if len(sys.argv)>2 else SECRET))
