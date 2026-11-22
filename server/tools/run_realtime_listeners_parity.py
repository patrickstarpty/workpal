"""Original Go full registerListeners, including typed personal payloads."""
from pathlib import Path
import copy,hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.infrastructure.events import EventBus
from workpal_backend.realtime.listeners import register_listeners
from workpal_backend.realtime.forwarding import PERSONAL_EVENTS
from workpal_backend.realtime.event_payloads import InvitationResponse,MemberWithUserResponse,StringPointer
from workpal_backend.realtime.metrics import RealtimeMetrics

def run(output):
    fixtures=[]
    def add(kind,payload,mode='',**fields):
        event=dict(type=kind,workspaceID='w',actorID='actor',actorType='member',payload=payload);event.update(fields)
        fixtures.append(dict(Event=event,Mode=mode,Recipients=[],Private=False,Failure=False))
    for kind in sorted(PERSONAL_EVENTS):
        for payload in [None,[],{}, {'recipient_id':'u'}, {'item':{'recipient_id':'nested'}}, {'recipient_id':'u','item':{'recipient_id':'nested'}}, {'recipient_id':3,'item':{'recipient_id':'nested'}}]:
            add(kind,payload)
    for user in [None,'','u']:
        for mode in ['', 'invitation_pointer','invitation_struct']:
            add('invitation:created',{'invitation':{'id':'i','invitee_user_id':user,'inviter_name':'<name>','workspace_name':''}},mode)
        for mode in ['', 'revoked_pointer']:
            add('invitation:revoked',{'invitee_user_id':user},mode)
    for kind in ['invitation:accepted','invitation:declined']:
        for workspace in ['', 'w']:
            for actor in ['', 'u']:
                add(kind,{},workspaceID=workspace,actorID=actor)
    for mode in ['', 'member_struct']:
        for user in ['', 'u']:
            add('member:added',{'member':{'user_id':user,'name':'<name>','avatar_url':None}},mode)
    add('member:added',{'member':{'user_id':3}})
    add('inbox:new',{'item':{'recipient_id':'u'}},'bad_marshal')
    add('member:added',{'member':{'user_id':'u'}},'bad_marshal')
    add('issue:updated',{'prev_title':'hidden','issue':{'title':'shown'}})
    add('issue:updated',{});fixtures[-1].update(Private=True,Recipients=['u','u','v'])
    add('issue:updated',{});fixtures[-1].update(Private=True)
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_realtime_listeners"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /work/cmd/server/listeners.go /work/parity/listeners.go && cd /work && go build -mod=readonly -p=4 -o /out/realtime-listeners-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/realtime-listeners-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    python=[]
    class Recorder:
        def __init__(self):self.calls=[]
        def broadcast_to_scope(self,scope,identity,data):self.calls.append(dict(scope=scope,id=identity,exclude=[],data=data.decode()))
        def broadcast_to_workspace(self,identity,data):self.broadcast_to_scope('workspace',identity,data)
        def broadcast(self,data):self.broadcast_to_scope('global','',data)
        def send_to_user(self,identity,data,*exclude):self.calls.append(dict(scope='user',id=identity,exclude=list(exclude),data=data.decode()))
    for f in fixtures:
        event=copy.deepcopy(f['Event']);p=event['payload'];mode=f['Mode']
        if mode=='invitation_struct':p['invitation']=InvitationResponse(**p['invitation'])
        elif mode=='member_struct':p['member']=MemberWithUserResponse(**p['member'])
        elif mode=='invitation_pointer':
            v=p['invitation'].get('invitee_user_id');p['invitation']['invitee_user_id']=StringPointer(v) if isinstance(v,str) else None
        elif mode=='revoked_pointer':
            v=p.get('invitee_user_id');p['invitee_user_id']=StringPointer(v) if isinstance(v,str) else None
        elif mode=='bad_marshal':p['unsupported']=object()
        recorder=Recorder();metrics=RealtimeMetrics();bus=EventBus()
        def audience(event):
            if f['Failure']:raise RuntimeError('fixture unavailable')
            return f['Recipients'],f['Private']
        register_listeners(bus,recorder,audience=audience,metrics=metrics);bus.publish(event)
        python.append(dict(calls=recorder.calls,events=metrics.snapshot()['events_sent_by_type']))
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/cmd/server/listeners.go','server/go/internal/handler/invitation.go','server/go/internal/handler/workspace.go','server/tests/parity/go_realtime_listeners/main.go','server/src/workpal_backend/realtime/listeners.py','server/src/workpal_backend/realtime/event_payloads.py','server/src/workpal_backend/realtime/forwarding.py','server/src/workpal_backend/infrastructure/events.py']
    Path(output).write_text(json.dumps(dict(scope='Original full Go registerListeners typed-before-global routing, exact payload bytes including struct order/null/omitempty and string pointers, first workspace exclusion and event counts. Audience boundary injected. Not production producer/async Redis broadcaster integration, SQL or transport certification.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
