"""Execute original Go runConsumer against a scripted Redis boundary."""
from pathlib import Path
import asyncio,base64,hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.realtime.relay_consumer import ScopeConsumer
from workpal_backend.realtime.relay_frame import inject_event_id
from workpal_backend.realtime.stream_retention import RetentionConfig
from redis.exceptions import ResponseError

def run(output):
    fixtures=[dict(Mode=mode,Enabled=enabled) for mode in ['', 'nogroup','nil','read_error','cancel_error','ack_error','create_error','busy','expiry_error'] for enabled in [False,True]]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_relay_consumer"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/realtime/parity_consumer.go && cd /work && go build -mod=readonly -p=4 -o /out/relay-consumer-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/relay-consumer-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    async def observe(f):
        events=[];stop=asyncio.Event();mode=f['Mode']
        class Client:
            reads=0
            async def xgroup_create(self,key,group,*,id,mkstream):
                assert mkstream
                events.append(['create',key,group,id])
                if mode=='create_error':raise ResponseError('create unavailable')
                if mode=='busy':raise ResponseError('BUSYGROUP exists')
                return True
            async def pexpire(self,key,ttl):
                events.append(['expire',key,ttl*1000000])
                if mode=='expiry_error':raise ResponseError('expiry unavailable')
                return True
            async def zadd(self,key,mapping):events.append(['register',key,next(iter(mapping))]);return 1
            async def xreadgroup(self,group,consumer,streams,*,count,block):
                key=next(iter(streams));events.append(['read',group,consumer,[key,streams[key]],count,block]);self.reads+=1
                if self.reads==1:
                    if mode=='nogroup':raise ResponseError('NOGROUP lost')
                    if mode=='nil':return []
                    if mode=='read_error':raise ResponseError('read unavailable')
                    if mode=='cancel_error':stop.set();raise ResponseError('read unavailable')
                delivery_read=2 if mode in ('nogroup','nil','read_error') else 1
                if self.reads==delivery_read:return [(key,[('1-0',{'payload_json':b'{"type":"x"}','event_id':'e','scope':'daemon_runtime','scope_id':'other'}),('2-0',{'event_id':'invalid'}),('3-0',{'payload_json':b'opaque','event_id':'f'})])]
                stop.set();return []
            async def xack(self,key,group,identity):
                events.append(['ack',key,group,identity])
                if mode=='ack_error':raise ResponseError('ack unavailable')
                return 1
            async def xgroup_delconsumer(self,key,group,name):events.append(['clean',key,group,name]);return 0
        async def deliver(e):
            assert e.scope=='daemon_runtime'
            events.append(['deliver',e.scope_id,base64.b64encode(inject_event_id(e.payload_json,e.event_id)).decode(),e.event_id])
        client=Client();c=ScopeConsumer(client,client,'node','daemon_runtime','runtime',deliver,retention=RetentionConfig(enabled=f['Enabled']))
        await c.run(stop)
        m=c.metrics
        return dict(events=events,metrics=[m.xread_total,m.xread_errors,m.ack_total,m.stream_missing_total,m.retention_errors])
    python=[asyncio.run(observe(f)) for f in fixtures]
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/realtime/redis_relay.go','server/go/internal/realtime/stream_retention.go',
             'server/tests/parity/go_relay_consumer/main.go','server/tests/parity/go_relay_consumer/wrapper.go',
             'server/src/workpal_backend/realtime/relay_consumer.py','server/src/workpal_backend/realtime/stream_retention.py',
             'server/src/workpal_backend/realtime/relay_envelope.py','server/src/workpal_backend/realtime/relay_frame.py']
    Path(output).write_text(json.dumps(dict(scope='Original Go runConsumer with scripted Redis network boundary: command sequence/options, daemon frame bytes, scope fallback, ACK and error/retention counters. Registry expiry clock excluded. No live Go Redis/network timing, Hub fanout, application wiring, consumer manager, heartbeat or sweeper certified.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},binary_sha256=hashlib.sha256((binaries/'relay-consumer-oracle').read_bytes()).hexdigest()),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
