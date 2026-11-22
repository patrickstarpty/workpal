"""Original Go Redis envelope primitives, comparing every field as bytes."""
from pathlib import Path
import base64,hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.realtime.relay_envelope import new_envelope,redis_values,envelope_from_values,peek_type_actor,stream_key,nodes_key,heartbeat_key

def run(output):
    frames=[b'{ "type":"chat:message", "actor_id":"u", "payload":9007199254740993 }',
        b'{"type":"x","actor_id":3,"actor_id":"u"}',b'{"type":7,"actor_id":"u"}',
        b'{"TYPE":"x","ACTOR_ID":"u","type":null}',b'{"type":"x",}',b'null',b'[]',b'opaque\xff',
        b'{"type":"x","extra":'+b'['*2000+b'0'+b']'*2000+b'}']
    fixtures=[]
    for index,frame in enumerate(frames):
        fixtures.append(dict(Frame=base64.b64encode(frame).decode(),Values={'payload_json':{'base64':base64.b64encode(frame).decode()},'event_id':17,'scope':'chat'},Nanos=[0,1234000000,-1][index%3]))
    for value in ['',None,True,3,{},'opaque']:
        fixtures.append(dict(Frame='',Values={'payload_json':value,'node_id':{'base64':'/w=='}},Nanos=0))
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_relay_envelope"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/realtime/parity_envelope.go && cd /work && go build -mod=readonly -p=4 -o /out/relay-envelope-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/relay-envelope-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    python=[]
    def encoded(envelope):return {key:base64.b64encode(value).decode() for key,value in redis_values(envelope).items()}
    for f in fixtures:
        frame=base64.b64decode(f['Frame'])
        values={key:base64.b64decode(value['base64']) if isinstance(value,dict) and 'base64' in value else value for key,value in f['Values'].items()}
        created=new_envelope('n','workspace_member','w:u','except',frame,'id',clock_ns=lambda:f['Nanos'])
        read,valid=envelope_from_values(values)
        python.append(dict(new=encoded(created),read=encoded(read),valid=valid,peek=list(peek_type_actor(frame)),keys=[stream_key('chat','a:b'),nodes_key('',''),heartbeat_key('n')]))
    if len(go)!=len(python):raise RuntimeError('missing observations')
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/realtime/redis_relay.go','server/tests/parity/go_relay_envelope/wrapper.go','server/tests/parity/go_relay_envelope/main.go','server/src/workpal_backend/realtime/relay_envelope.py','server/src/workpal_backend/realtime/frame_decode.py']
    Path(output).write_text(json.dumps(dict(scope='Original Go newEnvelope/Redis values/parse/peek/key helpers. Every Redis field compared as base64 bytes, payload unchanged. Creation time normalized by replacing Go CreatedAt with Go formatting of the fixture clock. No XADD, relay lifecycle, replay or transport equivalence certified.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},binary_sha256=hashlib.sha256((binaries/'relay-envelope-oracle').read_bytes()).hexdigest()),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
