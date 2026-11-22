"""Compare the original Go event bus with Python using isolated fixtures."""
from pathlib import Path
import hashlib
import json
import sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.infrastructure.events import EventBus


def run(output):
    cases=['copy','subscriptions','reentrant','nil-and-global-failure','empty']
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_event_bus"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cd /work && go build -mod=readonly -p=4 -o /out/event-bus-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/event-bus-oracle'],input=json.dumps(cases))
    go=json.loads(result.stdout)
    python=[]
    def failed(event):raise RuntimeError('fixture listener failure')
    for case in cases:
        bus=EventBus();trace=[];counts=[];original={}
        if case=='copy':
            original=dict(type='agent:status',workspaceID='workspace',payload={'value':'old'})
            def mutate(event):
                event['type']='changed';event['workspaceID']='other';event['payload']['value']='new'
            bus.subscribe('agent:status',mutate)
            bus.subscribe_all(lambda event:trace.append(event['type']+'/'+event['workspaceID']+'/'+event['payload']['value']))
            bus.publish(original)
        elif case=='subscriptions':
            def first(event):
                trace.append('first');bus.subscribe('x',lambda event:trace.append('late'));bus.subscribe_all(lambda event:trace.append('late-global'))
            bus.subscribe('x',first);bus.subscribe_all(lambda event:trace.append('global'))
            counts.extend([bus.subscriber_count('x'),bus.subscriber_count('missing')]);bus.publish({'type':'x'});counts.append(bus.subscriber_count('x'))
            trace.append('second-publish');bus.publish({'type':'x'});counts.append(bus.subscriber_count('x'))
        elif case=='reentrant':
            def nested(event):trace.append('outer');bus.publish({'type':'nested'})
            bus.subscribe('x',failed);bus.subscribe('x',nested);bus.subscribe('nested',lambda event:trace.append('nested'))
            bus.subscribe_all(lambda event:trace.append('global:'+event['type']));bus.publish({'type':'x'})
        elif case=='nil-and-global-failure':
            bus.subscribe('x',None);bus.subscribe_all(failed);bus.subscribe_all(lambda event:trace.append('survived'));bus.publish({'type':'x'})
        else:bus.subscribe_all(lambda event:trace.append('global:'+event.get('type','')));bus.publish({})
        python.append(dict(trace=trace,counts=counts,original=original))
    if len(go)!=len(python):raise RuntimeError('missing observations')
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/events/bus.go','server/tests/parity/go_event_bus/main.go',
             'server/src/workpal_backend/infrastructure/events.py']
    Path(output).write_text(json.dumps(dict(scope='Actual Go event bus callback order, registration counts, shallow event copy, shared payload, reentrant calls and failure isolation. Cross-thread scheduling and Redis/listener topology not certified.',
        fixtures=cases,go=go,python=python,mismatches=mismatches,
        source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},
        binary_sha256=hashlib.sha256((binaries/'event-bus-oracle').read_bytes()).hexdigest()),indent=2)+'\n')
    print(json.dumps(dict(cases=len(cases),mismatches=mismatches)))
    return bool(mismatches)

if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
