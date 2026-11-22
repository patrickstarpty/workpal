"""Original Go sharded config, duration formatting and scope hash routing."""
from pathlib import Path
from dataclasses import asdict,replace
import base64,hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.realtime.sharded_config import ShardedConfig,duration_text,shard_for

def run(output):
    names=['Shards','StreamMaxLen','ReadCount','ReadBlock','ReplayGrace','TrimHorizon','StreamTTL','TTLRefreshInterval','MaintenanceInterval','StreamTTLEnabled']
    attrs=list(asdict(ShardedConfig()))
    keys=[(b'workspace',b'w'),(b'ab',b'c'),(b'a',b'bc'),('中文'.encode(),b'id'),(b'scope',b'\xff'),(b'',b'')]
    configs=[ShardedConfig(),ShardedConfig().with_defaults(),ShardedConfig(replay_ns=3,trim_ns=3,ttl_ns=2),ShardedConfig(replay_ns=1<<62),ShardedConfig(replay_ns=(1<<63)-1),ShardedConfig(shards=(1<<32)+1)]
    for attr in attrs[:-1]:
        for value in [-1,0,1,(1<<63)-1]:configs.append(replace(ShardedConfig().with_defaults(),**{attr:value}))
    configs.append(replace(ShardedConfig().with_defaults(),enabled=True))
    fixtures=[dict(Config={name:getattr(c,attr) for name,attr in zip(names,attrs)},Keys=[dict(Scope=base64.b64encode(scope).decode(),ID=base64.b64encode(identity).decode()) for scope,identity in keys]) for c in configs]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_sharded_config"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/realtime/parity_sharded_config.go && cd /work && go build -mod=readonly -p=4 -o /out/sharded-config-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/sharded-config-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    python=[]
    for c in configs:
        error=normalized_error=''
        try:c.validate()
        except ValueError as caught:error=str(caught)
        n=c.with_defaults()
        try:n.validate()
        except ValueError as caught:normalized_error=str(caught)
        r=n.retention_config()
        python.append(dict(normalized=[getattr(n,attr) for attr in attrs],error=error,normalized_error=normalized_error,hashes=[shard_for(scope.decode('utf8',errors='surrogateescape'),identity.decode('utf8',errors='surrogateescape'),n.shards) for scope,identity in keys],retention=[r.max_len,r.trim_ns,r.ttl_ns,r.refresh_ns,r.maintenance_ns,r.enabled],durations=[duration_text(getattr(c,attr)) for attr in attrs[3:9]]))
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/realtime/sharded_stream_relay.go','server/go/internal/realtime/stream_retention.go','server/tests/parity/go_sharded_config/main.go','server/tests/parity/go_sharded_config/wrapper.go','server/src/workpal_backend/realtime/sharded_config.py','server/src/workpal_backend/realtime/stream_retention.py']
    Path(output).write_text(json.dumps(dict(scope='Original Go sharded config Normalized/Validate/RetentionConfig, duration text and FNV32a scope+NUL+ID hashing. Includes signed-duration overflow and uint32 shard divisor cast. No stream IO/lifecycle certification.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),hash_cases=len(fixtures)*len(keys),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
