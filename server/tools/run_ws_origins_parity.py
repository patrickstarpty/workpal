"""Original realtime.checkOrigin and net/url host/trusted-proxy observations."""
from pathlib import Path
import hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.realtime.origins import OriginPolicy,url_host

def run(output):
    origins=['','https://host','HTTP://HOST/path?x=1#fragment','//host','///host','http:/host','wss://host',
        'http://user:p@ss@host','http://user%20name@host','http://ü@host','http://host:80','http://host:bad','http://host:',
        'http://host:80:90','ws://host:80:90','http://host/%zz','http://host/?x=%zz','http://host/#%zz',
        'http://h%6fst','http://host%25','http://%C3%BC','http://[::1]','http://[::1%25eth0]',
        'http://[::1%25eth%20zero]','http://[127.0.0.1]','http://[broken]','http://host[::1]',
        'http://host]','http://host\\evil','http://host\t','http://host/#\x00',' http://host',
        'host','1a:host','scheme:opaque%zz','https://K','https://k','https://ſ','https://S','https://ß','https://SS',
        'https://allowed.example','https://host?x=1','https://host/path','https://host:99999','http://<host>','http://"host"']
    fixtures=[dict(Origin=origin,Host=host,Remote='127.0.0.1:1000',Forwarded=' host, proxy',Allowed=['https://allowed.example'],Proxies=['127.0.0.0/8']) for origin in origins for host in ['host','HOST','', '[::1]', 'k','SS']]
    fixtures.extend(dict(Origin='https://public',Host='internal',Remote=remote,Forwarded=' public, inner ',Allowed=[],Proxies=proxies)
        for remote in ['127.0.0.1:80','127.1.2.3:','[::1]:80','[::ffff:127.0.0.1]:80','::1','[::1]','[::1%eth0]:80','192.0.2.1:80','localhost:80','127.0.0.1:bad','127.0.0.01:80']
        for proxies in [[],['127.0.0.1/8'],['::1/128'],['::ffff:127.0.0.0/104'],['0.0.0.0/00'],['127.0.0.1'],['invalid','0.0.0.0/0','::/0']])
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_ws_origins"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/realtime/parity_ws_origins.go && cd /work && go build -mod=readonly -p=4 -o /out/ws-origins-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/ws-origins-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    python=[]
    for f in fixtures:
        policy=OriginPolicy(f['Allowed'],f['Proxies']);host='';valid=True
        try:host=url_host(f['Origin'])
        except ValueError:valid=False
        python.append(dict(allowed=policy.allowed(f['Origin'],f['Host'],f['Remote'],f['Forwarded']),trusted=policy.trusted(f['Remote']),host=host,valid_url=valid))
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/realtime/hub.go','server/tests/parity/go_ws_origins/main.go',
             'server/tests/parity/go_ws_origins/wrapper.go','server/src/workpal_backend/realtime/origins.py','server/tools/run_ws_origins_parity.py']
    Path(output).write_text(json.dumps(dict(scope='Original realtime checkOrigin, trusted proxy matching and Go1.26.9 URL host validity against Python policy. Selected schemes, malformed URLs, Unicode folds, proxy CIDRs, IPv4-mapped and scoped IPv6. No actual upgrade transport, environment origin selection or complete URL grammar certification.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
