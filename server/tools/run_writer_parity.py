"""Original Go Client.trySend/writeBatch with real loopback WebSocket frames."""
from pathlib import Path
import base64,asyncio,hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.realtime.writer import QueuedWriter

def run(output):
    fixtures=[dict(Count=count,DenyOn=deny,Inject=inject) for count,deny,inject in [
        (0,0,False),(1,0,False),(31,0,False),(32,0,False),(33,0,False),(65,0,False),
        (256,0,False),(257,0,False),(70,1,False),(70,2,False),(1,2,True),(32,2,True),(33,2,True),(256,0,True)]]
    fixtures += [dict(Count=count,DenyOn=deny,Inject=inject,Finish=True) for count,deny,inject in [(0,0,False),(65,0,False),(256,0,False),(65,2,False),(32,0,True)]]
    fixtures.extend(dict(Count=1,DenyOn=0,Inject=False,Finish=True,Frames=[base64.b64encode(raw).decode()]) for raw in [b'',b'opaque\xff',b'\xed\xa0\x80',b'\xc0\xaf',b'\x00\xfe',b'x'*126+b'\xff',b'x'*65536+b'\xff'])
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_writer"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/realtime/parity_writer.go && cd /work && go build -mod=readonly -p=4 -o /out/writer-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/writer-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    async def observe(f):
        frames=[];lookups=0;injected=False;close_code=0
        async def authorize():
            nonlocal lookups,injected
            lookups+=1
            if f['Inject'] and lookups==1:injected=writer.try_send(b'late')
            if f['DenyOn'] and lookups>=f['DenyOn']:raise PermissionError('revoked')
        async def write(frame):frames.append(base64.b64encode(frame).decode() if 'Frames' in f else frame.decode())
        async def failure():
            nonlocal close_code
            if f.get('Finish'):close_code=1006
        async def drained():
            nonlocal close_code
            close_code=1005
        writer=QueuedWriter(authorize,write,failure,on_drained=drained)
        payloads=[base64.b64decode(raw) for raw in f['Frames']] if 'Frames' in f else [str(i).encode() for i in range(f['Count'])]
        accepted=[writer.try_send(raw) for raw in payloads]
        after_finish=None
        if f.get('Finish'):
            writer.finish();after_finish=writer.try_send(b'after')
        await writer.flush();await writer.stop()
        return dict(accepted=accepted,frames=frames,lookups=lookups,injected=injected,after_finish=after_finish,close_code=close_code)
    python=[asyncio.run(observe(f)) for f in fixtures]
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/realtime/hub.go','server/go/internal/realtime/membership.go','server/go/internal/realtime/membership_batch.go',
             'server/tests/parity/go_writer/main.go','server/tests/parity/go_writer/wrapper.go',
             'server/src/workpal_backend/realtime/writer.py']
    Path(output).write_text(json.dumps(dict(scope='Actual original Go trySend/writeBatch writes real loopback WebSocket text frames. Compare queue overflow, 32-frame batch boundaries, query counts, denial and arrivals during lookup. Python writer callback captures frames; real Python WebSocket covered separately by integration suite. Finish cases execute original writePump and compare received close code (empty close1005 vs abrupt denial1006); Python callback observes intended termination, with actual Python empty close bytes separately tested on wsproto. Does not certify cross-socket membership cohort/worker pool, timed deadlines, ping frames or raw invalid UTF8 transport.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},binary_sha256=hashlib.sha256((binaries/'writer-oracle').read_bytes()).hexdigest()),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
