from pathlib import Path
import asyncio,hashlib,json,sys,uuid,time
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.realtime.redis_client import RelayRedis
from workpal_backend.realtime.relay_consumer import ScopeConsumer

async def observe(port):
    write=RelayRedis(host='127.0.0.1',port=port)
    read=RelayRedis(host='127.0.0.1',port=port)
    stop=asyncio.Event();task=None
    async def deliver(event):raise AssertionError('Unexpected event in empty stream')
    consumer=ScopeConsumer(write,read,'python-probe-node','chat','python-probe-chat',deliver)
    key='ws:scope:chat:python-probe-chat:stream';group='node:python-probe-node'
    try:
        task=asyncio.create_task(consumer.run(stop))
        async with asyncio.timeout(10):
            while True:
                try:ready=await write.xinfo_consumers(key,group)
                except Exception:ready=[]
                if ready:break
                await asyncio.sleep(.001)
        start=time.monotonic();stop.set();await asyncio.wait_for(task,8)
        elapsed=time.monotonic()-start
        consumers=await write.xinfo_consumers(key,group)
        return dict(stop_seconds=elapsed,consumers_after_wait=len(consumers),context_timeout_enabled=False)
    finally:
        stop.set()
        if task is not None:await task
        await write.aclose();await read.aclose()

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
    command(['docker','network','create',network])
    try:
        command(['docker','run','--rm','--pull','never','-d','--name',container,'--network',network,'--network-alias','redis','-p','127.0.0.1::6379','redis:7.4.7','redis-server','--save','','--appendonly','no'])
        result=command(['docker','run','--rm','--network',network,'--platform','linux/amd64','-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0','/out/redis-stop-oracle','redis:6379'])
        go=json.loads(result.stdout)
        address=command(['docker','port',container,'6379/tcp']).stdout.strip()
        python=asyncio.run(observe(int(address.rsplit(':',1)[1])))
    finally:
        command(['docker','rm','-f',container])
        command(['docker','network','rm',network])
    sources=['server/go/internal/realtime/redis_relay.go','server/go/cmd/server/main.go','server/go/go.mod','server/tests/parity/go_redis_stop/main.go','server/tests/parity/go_redis_stop/wrapper.go','server/tools/run_redis_stop_parity.py','server/src/workpal_backend/realtime/redis_client.py','server/src/workpal_backend/realtime/relay_consumer.py','server/src/workpal_backend/infrastructure/redis_cancellation.py']
    failures=[]
    for name,value in [('go',go),('python',python)]:
        if not 4 <= value['stop_seconds'] <= 6.5:failures.append(name+': stop timing')
        if value['consumers_after_wait']!=0:failures.append(name+': residual consumer')
    Path(output).write_text(json.dumps(dict(scope='Original Go legacy runConsumer versus Python ScopeConsumer, real isolated Redis7.4.7 after XREADGROUP consumer registration, cancellation waits for5sBLOCK then removes consumer. Actual durations retained;4..6.5s assertion. No pool contention, reconnect/retry, late-message ACK or non-read timeout parity certified.',go=go,python=python,failures=failures,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(dict(go=go,python=python,failures=failures))
    return bool(failures)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
