"""Original Go scope consumer ownership transitions against cancellable Redis boundary."""
from pathlib import Path
import asyncio,hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.realtime.hub import Hub
from workpal_backend.realtime.relay_consumers import RelayConsumers
from workpal_backend.realtime.relay_publisher import RelayPublisher

def run(output):
    fixtures=[[dict(Op=op,ID=identity) for op,identity in steps] for steps in [
        [('start','a'),('start','a'),('start','b'),('stop','a'),('stop','a'),('start','a'),('stop_all',''),('start','c')],
        [('start','a'),('start','b'),('cancel',''),('start','c'),('stop','a'),('stop_all','')],
        [('cancel',''),('start','a'),('stop','a'),('stop_all','')],
    ]]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_relay_consumers"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/realtime/parity_consumers.go && cd /work && go build -mod=readonly -p=4 -o /out/relay-consumers-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/relay-consumers-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    async def observe(steps):
        ready=asyncio.Queue();cleaned=asyncio.Queue();counts={}
        class Client:
            async def xgroup_create(self,key,*args,**kwargs):counts['create:'+key]=counts.get('create:'+key,0)+1;return True
            async def zadd(self,*args,**kwargs):return 1
            async def xreadgroup(self,*args,**kwargs):await ready.put(True);await asyncio.Event().wait()
            async def xgroup_delconsumer(self,key,*args):counts['clean:'+key]=counts.get('clean:'+key,0)+1;await cleaned.put(key);return 0
        client=Client();h=Hub();parent=asyncio.Event();manager=RelayConsumers(h,RelayPublisher(client,'node'));manager.bind(parent);out=[]
        try:
            for step in steps:
                op,identity=step['Op'],step['ID'];key=('chat',identity)
                if op=='start':
                    fresh=not manager._stopping and not parent.is_set() and key not in manager._consumers
                    manager.start_scope(*key)
                    if fresh:await asyncio.wait_for(ready.get(),1)
                elif op=='stop':
                    exists=key in manager._consumers
                    manager.stop_scope(*key)
                    if exists:
                        # Parent/global stop may already have cleaned the entry.
                        if manager._tasks and not parent.is_set() and not manager._stopping:await asyncio.wait_for(cleaned.get(),1)
                elif op=='stop_all':manager.stop();await manager.wait()
                else:parent.set();await manager.wait()
                out.append(dict(keys=sorted(i for _,i in manager._consumers),counts=dict(counts)))
        finally:parent.set();manager.stop();await manager.wait();await h.close()
        return out
    python=[asyncio.run(observe(f)) for f in fixtures]
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/realtime/redis_relay.go','server/tests/parity/go_relay_consumers/main.go',
             'server/tests/parity/go_relay_consumers/wrapper.go','server/src/workpal_backend/realtime/relay_consumers.py',
             'server/src/workpal_backend/realtime/relay_consumer.py']
    Path(output).write_text(json.dumps(dict(scope='Original Go startConsumer/stopConsumer/Stop/Wait ownership with blocking cancellable Redis boundary; compare map entries and group create/consumer cleanup counts across duplicate starts, restart, parent cancellation and permanent stop. Does not execute full RedisRelay.Start heartbeat/sweeper/ping, certify rapid overlapping same-scope cleanup races or real Redis transport timing.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},binary_sha256=hashlib.sha256((binaries/'relay-consumers-oracle').read_bytes()).hexdigest()),indent=2)+'\n')
    print(json.dumps(dict(scripts=len(fixtures),transitions=sum(map(len,fixtures)),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
