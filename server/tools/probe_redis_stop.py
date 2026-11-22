from pathlib import Path
import hashlib,json,sys,uuid
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
def run(output):
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_redis_stop"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/realtime/parity_redis_stop.go && cd /work && go build -mod=readonly -p=4 -o /out/redis-stop-oracle ./parity'])
    network='workpal-redis-stop-'+uuid.uuid4().hex
    container=network+'-redis'
    command(['docker','network','create','--internal',network])
    try:
        command(['docker','run','--rm','--pull','never','-d','--name',container,'--network',network,'--network-alias','redis','redis:7.4.7','redis-server','--save','','--appendonly','no'])
        result=command(['docker','run','--rm','--network',network,'--platform','linux/amd64','-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0','/out/redis-stop-oracle','redis:6379'])
        go=json.loads(result.stdout)
    finally:
        command(['docker','rm','-f',container])
        command(['docker','network','rm',network])
    sources=['server/go/internal/realtime/redis_relay.go','server/go/cmd/server/main.go','server/go/go.mod','server/tests/parity/go_redis_stop/main.go','server/tests/parity/go_redis_stop/wrapper.go','server/tools/probe_redis_stop.py']
    Path(output).write_text(json.dumps(dict(scope='Original Go legacy relay stopConsumer/Wait against isolated real Redis7.4.7, after server confirms XREADGROUP consumer registration. Uses production default ContextTimeoutEnabled=false. Reference timing probe only, no full lifecycle parity.',observation=go,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(go)
if __name__=='__main__':run(sys.argv[1])
