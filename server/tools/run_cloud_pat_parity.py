"""Actual Go Fleet verifier against an offline HTTP fixture; no production traffic."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import httpx
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.auth.cloud_pat import CloudPATVerifier, CloudPATInvalid, CloudPATUnavailable
SECRET='unused-public-fixture'

def run(output):
    bodies=['{"valid":true,"owner_id":"owner","instance_id":"i","instance_record_id":"r"}',
        '{"valid":false}', '{}', 'null', '[]', '{"valid":true}', '{"valid":"true"}',
        '{"valid":true,"owner_id":7}', '{"valid":true,"owner_id":"owner"} trailing',
        '{"VALID":true,"OWNER_ID":"owner"}', '{"valid":null}', '{"valid":true,"owner_id":"owner","owner_id":null}',
        '{"valid":true,"owner_id":7,"owner_id":"owner"}', '{"valid":true,"owner_id":"owner","unknown":7}']
    cases=[dict(body=body,status=200,token='mcn_fixture',owner='exists') for body in bodies]
    cases += [dict(body=bodies[0],status=status,token='mcn_fixture',owner='exists') for status in (201,400,401,403,429,500,503)]
    cases += [dict(body=bodies[0],status=200,token='mcn_fixture',owner=owner) for owner in ('missing','error')]
    cases += [dict(body=bodies[0],status=200,token=token,owner='exists') for token in ('','mcn_'+'x'*4096,'mcn_<&>')]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    subprocess.run(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_cloud_pat"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cd /work && go build -mod=readonly -p=4 -o /out/cloud-pat-oracle ./parity'],check=True)
    result=subprocess.run(['docker','run','--rm','--platform','linux/amd64','--network','none','-i',
        '-e','JWT_SECRET='+SECRET,'-v',f'{binaries}:/out:ro',
        'sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0','/out/cloud-pat-oracle'],
        input=json.dumps(cases),text=True,capture_output=True,check=True)
    go=json.loads(result.stdout)
    python=[]
    for case in cases:
        calls=[]; owners=[]
        def respond(request):
            calls.append(dict(method=request.method,path=request.url.path,body=request.content.decode(),
                content_type=request.headers['content-type'],accept=request.headers['accept']))
            return httpx.Response(case['status'],content=case['body'])
        def lookup(owner):
            owners.append(owner)
            if case['owner']=='error':raise OSError('offline')
            return case['owner']=='exists'
        identity={'o':'','i':'','r':''};kind='ok'
        with httpx.Client(transport=httpx.MockTransport(respond)) as client:
            try:identity=CloudPATVerifier('http://fixture',client=client).verify(case['token'],lookup)
            except CloudPATInvalid:kind='invalid'
            except CloudPATUnavailable:kind='unavailable'
        python.append(dict(kind=kind,identity=identity,calls=calls,owners=owners))
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    if len(go)!=len(python):raise RuntimeError('missing observations')
    sources=['server/go/internal/auth/cloud_pat.go','server/tests/parity/go_cloud_pat/main.go']
    evidence=dict(scope='Fleet verifier identity/error and HTTP application request; offline, no Redis/HTTP middleware acceptance',
        test_only=True,fixtures=cases,go=go,python=python,mismatches=mismatches,go_exit_code=result.returncode,
        source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},
        binary_sha256=hashlib.sha256((binaries/'cloud-pat-oracle').read_bytes()).hexdigest())
    Path(output).write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps({'cases':len(cases),'mismatches':mismatches}))
    return bool(mismatches)

if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
