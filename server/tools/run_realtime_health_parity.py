"""Original Go realtime health handler against actual Python ASGI requests."""
from pathlib import Path
import asyncio,base64,hashlib,json,sys,tempfile
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.app import create_app
from workpal_backend.config import Settings
import httpx

def run(output):
    fixtures=[]
    def case(token='',host='127.0.0.1',headers=()):
        fixtures.append(dict(Token=token,Host=host,Headers=[dict(Name=k,Value=base64.b64encode(v).decode()) for k,v in headers]))
    for host in ['127.0.0.1','127.4.5.6','::1','::ffff:127.0.0.1','192.0.2.1','localhost','::1%lo0','','127.00.0.1','[::1]']:
        case(host=host)
    for name in ['X-Forwarded-For','X-Forwarded-Host','X-Forwarded-Proto','X-Real-Ip','Forwarded']:
        for value in [b'',b'  ',b'192.0.2.1',b'\xc2\xa0',b'\xa0',b'\xe2\x80\x83']:
            case(headers=[(name,value)])
        case(headers=[(name,b''),(name,b'public')])
    for token in [' fixture-token ','tökén']:
        for auth in [b'',b'Bearer',b'Bearer ',b'Basic fixture-token',b'Bearer wrong',('Bearer '+token.strip()).encode(),('bEaReR  '+token.strip()+'  ').encode(),('Bearer \u00a0'+token.strip()+'\u2003').encode()]:
            for host in ['127.0.0.1','192.0.2.1']:
                case(token,host,[('Authorization',auth),('Forwarded',b'public')])
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_realtime_health"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /reference/server/go/cmd/server/health_realtime.go /work/parity/health_realtime.go && cd /work && go build -mod=readonly -p=4 -o /out/realtime-health-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/realtime-health-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    async def observe():
        results=[]
        with tempfile.TemporaryDirectory(prefix='workpal-metrics-parity-') as temporary:
            for i,f in enumerate(fixtures):
                settings=Settings(database_url='sqlite:///'+str(Path(temporary)/f'{i}.sqlite'),upload_dir=Path(temporary)/'uploads',realtime_metrics_token=f['Token'])
                app=create_app(settings)
                async with app.router.lifespan_context(app):
                    transport=httpx.ASGITransport(app=app,client=(f['Host'],1234))
                    async with httpx.AsyncClient(transport=transport,base_url='http://testserver') as client:
                        response=await client.get('/health/realtime',headers=[(h['Name'].encode(),base64.b64decode(h['Value'])) for h in f['Headers']])
                        names=['content-type','cache-control','www-authenticate','x-content-type-options']
                        results.append(dict(status=response.status_code,headers={k:response.headers[k] for k in names if k in response.headers},body=base64.b64encode(response.content).decode()))
        return results
    python=asyncio.run(observe())
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/cmd/server/health_realtime.go','server/go/internal/realtime/metrics.go','server/go/internal/daemonws/metrics.go','server/tests/parity/go_realtime_health/main.go','server/src/workpal_backend/realtime/health.py','server/src/workpal_backend/realtime/metrics.py','server/src/workpal_backend/realtime/daemon_metrics.py','server/src/workpal_backend/realtime/relay_metrics.py','server/src/workpal_backend/app.py','server/src/workpal_backend/config.py']
    Path(output).write_text(json.dumps(dict(scope='Original Go realtimeMetricsHandler vs actual Python ASGI route: status, content-type/cache-control/auth/nosniff headers and complete response bytes, default live counter state. Loopback, forwarding, repeated headers, token and UTF8/invalid-byte headers. Transport-generated framing headers excluded. Does not certify daemonws producers or all upstream middleware.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
