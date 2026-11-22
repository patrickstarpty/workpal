"""Original Go member-removal parser and bounded invalidation queue."""
from pathlib import Path
import asyncio,base64,hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.realtime.member_removal import parse_removal,removal_candidate,RemovalQueue

def run(output):
    raw=b'{"type":"member:removed","payload":{"user_id":"u","workspace_id":"w"}}'
    frames=[raw,b'null',b'[]',b'not json member:',b'{"type":"member:removed"}',
        b'{"type":"member:removed","payload":{"user_id":"u","workspace_id":"other"}}',
        b'{"type":"member:removed","payload":{"user_id":3}}',
        b'{"type":"member:removed","payload":{"user_id":"u"},"payload":{"workspace_id":"w"},"payload":null}',
        b'{"type":"member:removed","payload":{"user_id":3},"payload":{"user_id":"u","workspace_id":"w"}}',
        b'{"TYPE":"memb\\u0065r:removed","PAYLOAD":{"USER_ID":"u","WORKSPACE_ID":"w"}}',
        b'{"type":"comment:created","actor_type":"member"}']
    for value in [b'null',b'3',b'true',b'[]',b'{}',b'"u"',b'"\\ud800"']:
        frames.append(b'{"type":"member:removed","payload":{"user_id":'+value+b',"workspace_id":"w"}}')
    for depth in [2000,9999,10000]:frames.append(raw[:-1]+b',"unknown":'+b'['*depth+b'0'+b']'*depth+b'}')
    fixtures=[dict(Kind='parse',Raw=base64.b64encode(frame).decode()) for frame in frames]
    fixtures += [dict(Kind='queue',Mode=mode,Count=count) for mode in ['member','removed','error'] for count in [1,2,67]]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_member_removal"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/realtime/parity_removal.go && cd /work && go build -mod=readonly -p=4 -o /out/member-removal-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/member-removal-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    async def observe(f):
        if f['Kind']=='parse':
            raw=base64.b64decode(f['Raw']);user,removal=parse_removal('w',raw)
            return dict(candidate=removal_candidate(raw),user=user,removal=removal)
        entered=asyncio.Queue();release=asyncio.Event();clients=['target'];stopped=set();frames=[]
        async def check(w,u):
            await entered.put(True);await release.wait()
            if f['Mode']=='error':raise OSError('lookup unavailable')
            return f['Mode']=='member'
        def snapshot(w,u):return tuple(clients),check
        def peers(w,raw,event,user):frames.append(raw.decode())
        async def stop(client,notice,deadline):stopped.add(client)
        queue=RemovalQueue(snapshot,peers,stop)
        raw=b'{"type":"member:removed","payload":{"user_id":"u","workspace_id":"w"}}'
        handled=[]
        for i in range(f['Count']):
            handled.append(queue.intercept('w',raw,str(i)))
            if i<2:await entered.get()
        pending,dropped=queue.pending,queue.dropped;clients.append('late');release.set()
        await queue.join();await queue.close()
        return dict(handled=handled,pending_before_release=pending,dropped=dropped,peer_frames=frames,target_stopped='target' in stopped,late_stopped='late' in stopped)
    python=[asyncio.run(observe(f)) for f in fixtures]
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/realtime/membership.go','server/go/internal/realtime/membership_removal.go',
             'server/tests/parity/go_member_removal/main.go','server/tests/parity/go_member_removal/wrapper.go',
             'server/src/workpal_backend/realtime/member_removal.py','server/src/workpal_backend/realtime/frame_decode.py']
    Path(output).write_text(json.dumps(dict(scope='Original Go parseMemberRemoval and queueMemberRemoval/runMemberRemovals with real Hub/Client channels and controlled membership checker. Compare parsing, peer frame order, snapshots, overflow counters and stopped target state. Python callbacks model Hub/transport boundary; production Hub wiring/notice timing/raw transport/metrics endpoint not certified.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},binary_sha256=hashlib.sha256((binaries/'member-removal-oracle').read_bytes()).hexdigest()),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
