"""Run original Go registerListeners against an isolated recording broadcaster."""
from pathlib import Path
import hashlib
import json
import sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.realtime.forwarding import forward_workspace_event
from workpal_backend.realtime.metrics import RealtimeMetrics
from workpal_backend.realtime.protocol import private_kind,project_event,resolve_audience
from workpal_backend.infrastructure.go_response import marshal_map_json


def run(output):
    fixtures=[]
    def add(kind,**fields):
        event=dict(type=kind,workspaceID='w',actorID='actor',actorType='member',payload={'html':'<>&\u2028','value':1e-7})
        event.update(fields)
        fixtures.append(dict(Event=event,Recipients=[],Private=False,Failure=False))
    for kind in ['chat:new','chat:future','task:message','task:failed','pin:created','pin:deleted','pin:reordered','issue_view_preference:changed','arbitrary']:
        add(kind,chatSessionID='chat',chatSessionOwnerID='owner',memberPrivateUserID='member')
        add(kind,chatSessionID='chat')
    add('task:message')
    add('chat:new',workspaceID='',chatSessionOwnerID='owner')
    add('arbitrary',workspaceID='',memberPrivateUserID='member')
    add('daemon:future',workspaceID='')
    add('arbitrary',workspaceID='')
    add('task:failed',payload={'error':'secret','task_id':'t'},chatSessionID='chat',chatSessionOwnerID='owner')
    add('issue:updated',payload={'prev_description':'secret','prev_title':'old','issue':{'title':'new'}})
    add('task:failed',payload=['error'])
    add('issue:updated');fixtures[-1].update(Private=True,Recipients=['u','u','v'])
    add('issue:updated');fixtures[-1].update(Private=True)
    add('issue:updated');fixtures[-1].update(Private=True,Recipients=None)
    add('issue:updated');fixtures[-1].update(Failure=True)
    for kind in ['inbox:new','inbox:read','invitation:created','invitation:revoked','issue_unread:changed']:
        add(kind,payload={})
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_realtime_forwarding"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /work/cmd/server/listeners.go /work/parity/listeners.go && cd /work && go build -mod=readonly -p=4 -o /out/realtime-forwarding-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/realtime-forwarding-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    python=[]
    class Recorder:
        def __init__(self):self.calls=[]
        def broadcast_to_scope(self,scope,identity,data):self.calls.append(dict(scope=scope,id=identity,data=data.decode()))
        def broadcast_to_workspace(self,identity,data):self.broadcast_to_scope('workspace',identity,data)
        def broadcast(self,data):self.broadcast_to_scope('global','',data)
    for fixture in fixtures:
        recorder=Recorder();metrics=RealtimeMetrics()
        def resolve(event):
            if fixture['Failure']:raise RuntimeError('fixture unavailable')
            return fixture['Recipients'],fixture['Private']
        forward_workspace_event(fixture['Event'],recorder,audience=resolve,metrics=metrics)
        python.append(dict(calls=recorder.calls,events=metrics.snapshot()['events_sent_by_type']))
    if len(go)!=len(python):raise RuntimeError('missing observations')
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    bridge=[]
    for index,fixture in enumerate(fixtures):
        event=fixture['Event']
        if not private_kind(event):continue
        frame=project_event(event,event.get('workspaceID'));audience=resolve_audience(event)
        calls=[] if audience is None else [dict(scope=audience[0],id=audience[1],data=marshal_map_json(frame).decode())]
        bridge.append(dict(case=index,python=calls,go=go[index]['calls']))
        if calls!=go[index]['calls']:mismatches.append('bridge:'+str(index))
    sources=['server/go/cmd/server/listeners.go','server/tests/parity/go_realtime_forwarding/main.go','server/src/workpal_backend/realtime/forwarding.py','server/src/workpal_backend/infrastructure/go_response.py','server/src/workpal_backend/realtime/protocol.py','server/src/workpal_backend/realtime/metrics.py']
    Path(output).write_text(json.dumps(dict(scope='Original Go registerListeners with isolated audience resolver and broadcaster. Compares global-listener routing and exact serialized bytes, plus supported private project_event/resolve_audience bridge decisions. Includes events_sent_by_type counts, including zero-recipient private events. Personal subscriber typed payloads, audience SQL/deadlines, transport, revocation and live wiring are not certified.',fixtures=fixtures,go=go,python=python,private_bridge=bridge,mismatches=mismatches,
        source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},binary_sha256=hashlib.sha256((binaries/'realtime-forwarding-oracle').read_bytes()).hexdigest()),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),private_bridge_cases=len(bridge),mismatches=mismatches)))
    return bool(mismatches)

if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
