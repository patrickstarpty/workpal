"""Original request/query cancellation response helpers versus Python."""
from pathlib import Path
import asyncio,hashlib,json,sys,subprocess
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.infrastructure.request_cancellation import cancellation_response

class QueryError(Exception):
    def __init__(self,code):self.sqlstate=code

def run(output):
    fixtures=[dict(Parent=parent,Operation=operation,Wrap=wrap) for parent in ['live','cancel','deadline'] for operation in ['none','cancel','deadline','other','57014','08006'] for wrap in ['none','wrap','join_cancel','join_sql']]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_request_cancellation"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/handler/parity_request_cancellation.go && cd /work && go build -mod=readonly -p=4 -o /out/request-cancellation-oracle ./parity'])
    go=[]
    for offset in range(0,len(fixtures),32):
        result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i','-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0','/out/request-cancellation-oracle'],input=json.dumps(fixtures[offset:offset+32]))
        go.extend(json.loads(result.stdout))
    python=[]
    for f in fixtures:
        parent=asyncio.CancelledError() if f['Parent']=='cancel' else TimeoutError() if f['Parent']=='deadline' else None
        error={'none':None,'cancel':asyncio.CancelledError(),'deadline':TimeoutError(),'other':RuntimeError(),'57014':QueryError('57014'),'08006':QueryError('08006')}[f['Operation']]
        if f['Wrap']=='wrap':
            outer=RuntimeError('operation');outer.__cause__=error;error=outer
        elif f['Wrap']=='join_cancel':error=BaseExceptionGroup('write failure',[v for v in [RuntimeError(),error,asyncio.CancelledError()] if v is not None])
        elif f['Wrap']=='join_sql':error=BaseExceptionGroup('query failure',[v for v in [QueryError('08006'),error,QueryError('57014')] if v is not None])
        direct=cancellation_response(parent,error);query=cancellation_response(parent,error,query=True)
        python.append(dict(direct=direct is not None,query=query is not None,status=direct.status_code if direct is not None else 200,query_status=query.status_code if query is not None else 200,body=direct.body.decode() if direct is not None else '',query_body=query.body.decode() if query is not None else ''))
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/handler/request_cancellation.go','server/go/internal/handler/search.go','server/tests/parity/go_request_cancellation/main.go','server/tests/parity/go_request_cancellation/wrapper.go','server/src/workpal_backend/infrastructure/request_cancellation.py','server/tools/run_request_cancellation_parity.py']
    Path(output).write_text(json.dumps(dict(scope='Original request/query cancellation helpers: actual parent context cancellation/deadline, wrapped and joined operation errors, PostgreSQL SQLSTATE selection, response status and empty body. Does not certify ASGI request-disconnect propagation or active query cancellation.',fixtures=fixtures,execution_batch_size=32,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':
    try:raise SystemExit(run(sys.argv[1]))
    except subprocess.CalledProcessError as error:
        print(error.stderr,file=sys.stderr)
        raise
