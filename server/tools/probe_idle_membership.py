from pathlib import Path
import hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
def run(output):
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_idle_membership"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/realtime/parity_idle_membership.go && cd /work && go build -mod=readonly -p=4 -o /out/idle-membership-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/idle-membership-oracle'])
    go=json.loads(result.stdout)
    assert go==dict(idle_lookup_count=0,write_lookup_count=1,close_code=1006),go
    sources=['server/go/internal/realtime/hub.go','server/go/internal/realtime/membership.go','server/tests/parity/go_idle_membership/main.go','server/tests/parity/go_idle_membership/wrapper.go']
    Path(output).write_text(json.dumps(dict(scope='Original Go readPump+writePump idle for700ms with rejecting membership checker: no idle lookups, next content write denied and TCP closed. Reference behavior probe only; Python application regression is test_idle_membership_removal_is_enforced_on_next_content_write.',observation=go,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(go)
if __name__=='__main__':run(sys.argv[1])
