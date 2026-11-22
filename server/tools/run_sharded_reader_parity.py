"""Original Go readShardOnce with actual Hub delivery at Redis boundary."""
from pathlib import Path
import asyncio,base64,hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.realtime.hub import Hub,Connection
from workpal_backend.realtime.sharded_config import ShardedConfig
from workpal_backend.realtime.sharded_reader import ShardReader
from workpal_backend.realtime.relay_consumer import _Stopped
from workpal_backend.realtime.relay_delivery import deliver_envelope
from workpal_backend.realtime.relay_metrics import RedisMetrics

def run(output):
    rows=[dict(ID=f'{i+1}-0',Values=value) for i,value in enumerate([
        {},{'payload_json':'missing scope'}, {'scope':'workspace','payload_json':'missing ID'},
        {'scope':'workspace','scope_id':'w','payload_json':'{"type":"fixture"}','event_id':'e'},
        {'scope':'workspace','scope_id':'w','payload_json':'{"type":"fixture"}','event_id':'e'},
        {'scope':'global','scope_id':'all','payload_json':'global'},
        {'scope':'workspace','scope_id':'foreign','payload_json':'hidden'},
        {'scope':'daemon_runtime','scope_id':'r','payload_json':'daemon'},
        {'scope':'workspace','scope_id':'w','payload_json':3},
    ])]
    fixtures=[dict(Error=error,Stop=stop,Last='0-0',Rows=rows,Block=0) for error in ['', 'nil','deadline','canceled','network'] for stop in [False,True]]
    fixtures.extend(dict(Error='',Stop=False,Last='123-4',Rows=selected,Block=block) for selected in [[],rows[:3],rows[3:5],rows[5:]] for block in [1,1_000_000,5_000_000_000])
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_sharded_reader"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/realtime/parity_sharded_reader.go && cd /work && go build -mod=readonly -p=4 -o /out/sharded-reader-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/sharded-reader-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    async def observe(f):
        calls=[];stop=asyncio.Event();h=Hub();metrics=RedisMetrics()
        class Socket:
            async def close(self,code):pass
        connection=Connection(Socket(),lambda:None,'w','u');h.register(connection)
        class Client:
            async def xread(self,streams,**kwargs):
                calls.append(dict(streams=[*streams.keys(),*streams.values()],**kwargs))
                if f['Stop']:stop.set()
                if f['Error']=='nil':return []
                if f['Error']=='deadline':raise TimeoutError('context deadline exceeded')
                if f['Error']=='canceled':raise _Stopped()
                if f['Error']=='network':raise RuntimeError('io unavailable')
                return [('ws:relay:shard:0',[(row['ID'],row['Values']) for row in f['Rows']])]
        reader=ShardReader(Client(),0,ShardedConfig(read_block_ns=f['Block']).with_defaults(),lambda envelope:deliver_envelope(h,envelope),metrics=metrics)
        reader.last_id=f['Last']
        try:
            more=await reader.read_once(stop);frames=[];queue=connection._writer._queue
            while not queue.empty():frames.append(base64.b64encode(queue.get_nowait()).decode());queue.task_done()
            return dict(calls=calls,more=more,last=reader.last_id,frames=frames,metrics=[metrics.xread_total,metrics.xread_errors,metrics.ack_total,metrics.last_error])
        finally:await h.close()
    python=[asyncio.run(observe(f)) for f in fixtures]
    assert len(go)==len(python)
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/realtime/sharded_stream_relay.go','server/tests/parity/go_sharded_reader/main.go','server/tests/parity/go_sharded_reader/wrapper.go','server/src/workpal_backend/realtime/sharded_reader.py','server/src/workpal_backend/realtime/sharded_config.py','server/src/workpal_backend/realtime/hub.py','server/src/workpal_backend/realtime/relay_delivery.py']
    Path(output).write_text(json.dumps(dict(scope='Original readShardOnce Redis arguments normalized to wire block milliseconds, cursor/return/metrics, invalid envelope advancement and actual Hub queue delivery. Nil/context/network error and parent-stop cases. No real Go Redis IO, generation reset loop or socket transport certification.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
