"""Actual Go Auth target-selector branch, scripted DB fixture; no task lifecycle claim."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from fastapi import HTTPException
from starlette.requests import Request
from workpal_backend.auth.task_workspace import check_target
SECRET='unused-public-fixture'
A='0a0a0a0a-0000-4000-8000-00000000000a'
B='0b0b0b0b-0000-4000-8000-00000000000b'

def run(output):
    queries=['','workspace_id='+A,'workspace_id='+B,'workspace_id=',
        'workspace_id='+A+'&workspace_id='+B,
        'workspace_slug=ws-a','workspace_slug=ws-b','workspace_slug=unknown',
        'workspace_slug=ws-db-error','workspace_slug=ws-a&workspace_slug=ws-b',
        'workspace_slug=ws%2Da&q=a%20b','workspace_id=nope',
        'workspace_id='+A+'&q=%zz','q=%','q=%0','q=;ignored=1',
        'workspace_id='+A.replace('-',''),'workspace_id='+A.upper(),
        'workspace_id='+A.replace('-','X'),'workspace_slug=&workspace_id=',
        'workspace_slug=ws-a&q=%3B']
    cases=[dict(Query=q,Headers={}) for q in queries]
    cases += [dict(Query=q,Headers=h) for q,h in [
        ('',{'X-Workspace-ID':[A,B]}),('',{'X-Workspace-ID':[A,A]}),
        ('',{'X-Workspace-Slug':['ws-a','ws-b']}),('',{'X-Workspace-Slug':['ws-a','ws-a']}),
        ('workspace_id='+B,{'X-Workspace-ID':['invalid']}),
        ('q=%zz',{'X-Workspace-ID':[B]}),
        ('workspace_slug=ws-a',{'X-Workspace-Slug':['ws-a']}),
        ('',{'X-Workspace-ID':[A],'X-Workspace-Slug':['ws-b']}),
        ('',{'X-Workspace-ID':['urn:uuid:'+A]}),
        ('',{'X-Workspace-ID':[''],'X-Workspace-Slug':['']})]]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    subprocess.run(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_task_target"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cd /work && go build -mod=readonly -p=4 -o /out/task-target-oracle ./parity'],check=True)
    result=subprocess.run(['docker','run','--rm','--platform','linux/amd64','--network','none','-i',
        '-e','JWT_SECRET='+SECRET,'-v',f'{binaries}:/out:ro',
        'sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0','/out/task-target-oracle'],
        input=json.dumps(cases),text=True,capture_output=True,check=True)
    go=json.loads(result.stdout)
    python=[]
    def lookup(slug):
        if slug=='ws-db-error':raise OSError('fixture DB failure')
        return {'ws-a':A,'ws-b':B}.get(slug)
    for case in cases:
        request=Request(dict(type='http',method='POST',path='/api/upload-file',
            query_string=case['Query'].encode(),headers=[(k.lower().encode(),v.encode())
                for k,values in case['Headers'].items() for v in values]))
        try:
            check_target(request,A,lookup)
            python.append(dict(status=204,body=''))
        except HTTPException as exc:
            python.append(dict(status=exc.status_code,body=json.dumps({'error':exc.detail},separators=(',',':'))))
    if len(go)!=len(python):raise RuntimeError('missing observations')
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/middleware/task_token_workspace.go','server/go/internal/middleware/auth.go',
        'server/go/internal/middleware/task_token_workspace_test.go','server/tests/parity/go_task_target/main.go']
    evidence=dict(scope='Task target-selector status/body only; actual Go Auth and scripted DB. No Python task token DB/auth lifecycle claim.',
        test_only=True,fixtures=cases,go=go,python=python,mismatches=mismatches,go_exit_code=result.returncode,
        source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},
        binary_sha256=hashlib.sha256((binaries/'task-target-oracle').read_bytes()).hexdigest())
    Path(output).write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps({'cases':len(cases),'mismatches':mismatches}))
    return bool(mismatches)

if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
