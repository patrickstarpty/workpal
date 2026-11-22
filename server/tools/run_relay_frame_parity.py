"""Original Go raw-message event-ID injection, preserving bytes and numbers."""
from pathlib import Path
import ast,base64,hashlib,json,sys
from export_go_schema import command
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'server/src'))
from workpal_backend.realtime.relay_frame import inject_event_id

def run(output):
    tree=ast.parse((ROOT/'server/tests/test_relay_frame_id.py').read_text())
    test=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='test_event_id_injection_preserves_raw_values')
    pairs=[(raw,event_id.encode()) for raw,event_id,_ in ast.literal_eval(test.decorator_list[0].args[1])]
    frames=[b'{}',b'{"Event_ID":"old"}',b'{"event_id":1,"event_id":2}',b'{"\\u0065vent_id":null}',
        b'{"html":"<>&","unicode":"\\u2028"}',b'{"invalid":"\xff"}',b'{"\xff":1}',b'{"x":"\\ud800"}',
        '{"汉字":"😀\u2028\u2029"}'.encode(),b'{"empty":[],"bool":true,"null":null}',
        b'{"x":1}  ',b'{"x":1} {}',b'{"x":NaN}',b'{"x":1e999}',b'{"x":-0.00e+00}']
    for depth in [900,2000,9999,10000]:frames.append(b'{"payload":'+b'['*depth+b'1e999'+b']'*depth+b'}')
    for frame in frames:
        for event_id in [b'id',b'<>&',b'\xff']:pairs.append((frame,event_id))
    fixtures=[dict(Frame=base64.b64encode(frame).decode(),ID=base64.b64encode(event_id).decode()) for frame,event_id in pairs]
    reference=ROOT/'.superpowers/sdd/2026-11-22-go-parity-plan/go-reference-v1'
    binaries=reference.parent/'go-binaries'
    command(['docker','run','--rm','--network','none','-v',f'{reference}:/reference:ro',
        '-v',f'{ROOT/"server/tests/parity/go_relay_frame"}:/harness:ro','-v',f'{binaries}:/out',
        '-v','workpal-go-parity-modcache:/go/pkg/mod','-v','workpal-go-parity-buildcache:/root/.cache/go-build',
        '-e','GOOS=linux','-e','GOARCH=amd64','-e','CGO_ENABLED=0','-e','GOWORK=off','-e','GOFLAGS=',
        '-e','GOMAXPROCS=4','golang:1.26.9','sh','-c',
        'mkdir -p /work/parity && cp -a /reference/server/go/. /work/ && cp /harness/main.go /work/parity/main.go && cp /harness/wrapper.go /work/internal/realtime/parity_frame_id.go && cd /work && go build -mod=readonly -p=4 -o /out/relay-frame-oracle ./parity'])
    result=command(['docker','run','--rm','--network','none','--platform','linux/amd64','-i',
        '-v',f'{binaries}:/out:ro','sha256:5d8d6618be1c45f3c48f2b6f6e3144147010b2ca7ca106756834987cdac4e0f0',
        '/out/relay-frame-oracle'],input=json.dumps(fixtures))
    go=json.loads(result.stdout)
    python=[base64.b64encode(inject_event_id(frame,event_id.decode('utf-8',errors='surrogateescape'))).decode() for frame,event_id in pairs]
    if len(go)!=len(python):raise RuntimeError('missing observations')
    mismatches=[i for i,(a,b) in enumerate(zip(go,python)) if a!=b]
    sources=['server/go/internal/realtime/redis_relay.go','server/tests/parity/go_relay_frame/wrapper.go','server/tests/parity/go_relay_frame/main.go','server/src/workpal_backend/realtime/relay_frame.py','server/src/workpal_backend/realtime/frame_decode.py','server/src/workpal_backend/infrastructure/go_response.py']
    Path(output).write_text(json.dumps(dict(scope='Actual Go injectEventID output bytes, preserving raw payload numeric/escape representation and invalid-input fallback, including observed nesting boundaries. No Redis publishing/receipts/transport coverage.',fixtures=fixtures,go=go,python=python,mismatches=mismatches,source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},binary_sha256=hashlib.sha256((binaries/'relay-frame-oracle').read_bytes()).hexdigest()),indent=2)+'\n')
    print(json.dumps(dict(cases=len(fixtures),mismatches=mismatches)))
    return bool(mismatches)
if __name__=='__main__':raise SystemExit(run(sys.argv[1]))
